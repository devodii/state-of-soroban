from pathlib import Path

import numpy as np

from state_of_soroban.analysis.cluster import top_terms
from state_of_soroban.analysis.records import (
    RepoText,
    RepoUsecase,
    UsecaseInfo,
    read_jsonl,
    write_jsonl,
)
from state_of_soroban.workflow import load_workflow


def run_usecases(repos_file: Path, out: Path) -> int:
    from fastembed import TextEmbedding
    from sklearn.cluster import MiniBatchKMeans

    config = load_workflow().analysis
    repos = list(read_jsonl(repos_file, RepoText))
    model = TextEmbedding(config.embed_model)
    vectors = np.array(list(model.embed([r.text for r in repos], batch_size=64)))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
    km = MiniBatchKMeans(
        n_clusters=config.usecase_clusters, random_state=0, n_init=3
    ).fit(vectors)
    stop = {*config.stop_words, *config.usecase_stop_words}
    terms = top_terms(repos, km.labels_, config, stop)
    sims = (vectors * km.cluster_centers_[km.labels_]).sum(axis=1)
    sims /= np.linalg.norm(km.cluster_centers_[km.labels_], axis=1) + 1e-9
    sizes = np.bincount(km.labels_)
    write_jsonl(
        out / "usecases.jsonl.gz",
        [
            UsecaseInfo(usecase=int(i), size=int(sizes[i]), terms=terms.get(i, []))
            for i in range(len(sizes))
        ],
    )
    write_jsonl(
        out / "repo_usecases.jsonl.gz",
        (
            RepoUsecase(repo=r.repo, usecase=int(km.labels_[i]), sim=float(sims[i]))
            for i, r in enumerate(repos)
        ),
    )
    return len(repos)
