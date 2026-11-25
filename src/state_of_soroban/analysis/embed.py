from pathlib import Path

import numpy as np

from state_of_soroban.analysis.records import Unit, read_jsonl
from state_of_soroban.workflow import load_workflow


def embed_shard(units_file: Path, index: int, count: int, out: Path) -> int:
    from fastembed import TextEmbedding

    model = TextEmbedding(load_workflow().analysis.embed_model)
    units = [
        unit
        for position, unit in enumerate(read_jsonl(units_file, Unit))
        if position % count == index
    ]
    vectors = np.array(
        list(model.embed([unit.text for unit in units], batch_size=128)),
        dtype=np.float32,
    )
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
    np.savez_compressed(out, vectors=vectors.astype(np.float16))
    return len(units)
