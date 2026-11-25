import logging
import re
from collections import Counter
from pathlib import Path

import numpy as np

from state_of_soroban.analysis.records import (
    ClusterInfo,
    Member,
    RunMetrics,
    Unit,
    read_jsonl,
    write_jsonl,
)
from state_of_soroban.workflow import Analysis, load_workflow

log = logging.getLogger("state_of_soroban")

TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def load_vectors(folder: Path, count: int) -> np.ndarray:
    parts = [
        np.load(folder / f"embed-{index}" / f"shard-{index}.npz")["vectors"]
        for index in range(count)
    ]
    matrix = np.zeros((sum(len(p) for p in parts), parts[0].shape[1]), np.float32)
    for index, part in enumerate(parts):
        matrix[index::count] = part
    return matrix


def merge_centroids(centroids: np.ndarray, distance: float) -> np.ndarray:
    from sklearn.cluster import AgglomerativeClustering

    merged = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=distance,
    ).fit(centroids)
    return merged.labels_


def top_terms(units: list[Unit], labels: np.ndarray, config: Analysis, stop: set[str]):
    documents: dict[int, Counter] = {}
    for unit, label in zip(units, labels, strict=True):
        counter = documents.setdefault(int(label), Counter())
        words = [w.lower() for w in TOKEN.findall(unit.text)]
        counter.update(w for w in words if w not in stop)
        counter.update(
            f"{a} {b}"
            for a, b in zip(words, words[1:], strict=False)
            if a not in stop and b not in stop
        )
    totals: Counter = Counter()
    for counter in documents.values():
        totals.update(counter)
    average = sum(totals.values()) / max(len(documents), 1)
    terms: dict[int, list[str]] = {}
    for label, counter in documents.items():
        scored = {
            term: count * np.log(1 + average / totals[term])
            for term, count in counter.items()
            if count >= 3
        }
        ranked = sorted(scored, key=scored.get, reverse=True)
        terms[label] = ranked[: config.terms]
    return terms


def stability(matrix: np.ndarray, labels: np.ndarray, config: Analysis) -> tuple:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import adjusted_mutual_info_score

    rng = np.random.default_rng(7)
    size = int(len(matrix) * config.stability_sample)
    chosen = rng.choice(len(matrix), size, replace=False)
    second = MiniBatchKMeans(
        n_clusters=max(min(config.clusters // 3, size // 10), 2),
        random_state=99,
        n_init=1,
        batch_size=8192,
    ).fit(matrix[chosen])
    return (
        float(adjusted_mutual_info_score(labels[chosen], second.labels_)),
        size,
    )


def run_cluster(units_file: Path, embeds: Path, count: int, out: Path) -> RunMetrics:
    from sklearn.cluster import MiniBatchKMeans

    config = load_workflow().analysis
    units = list(read_jsonl(units_file, Unit))
    matrix = load_vectors(embeds, count)
    log.info("clustering %s units", len(units))
    micro = MiniBatchKMeans(
        n_clusters=min(config.clusters, len(units) // 10),
        random_state=0,
        n_init=1,
        batch_size=8192,
        max_iter=60,
    ).fit(matrix)
    centroids = micro.cluster_centers_ / (
        np.linalg.norm(micro.cluster_centers_, axis=1, keepdims=True) + 1e-9
    )
    parent = merge_centroids(centroids, config.merge_distance)
    labels = parent[micro.labels_]
    macro = {}
    for label in np.unique(labels):
        mean = matrix[labels == label].mean(axis=0)
        macro[int(label)] = mean / (np.linalg.norm(mean) + 1e-9)
    sims = np.array(
        [float(matrix[i] @ macro[int(labels[i])]) for i in range(len(units))]
    )
    stop = set(config.stop_words)
    terms = top_terms(units, labels, config, stop)
    sizes = Counter(int(label) for label in labels)
    infos = []
    for label, size in sizes.items():
        members = np.where(labels == label)[0]
        best = members[np.argsort(-sims[members])[: config.medoids]]
        infos.append(
            ClusterInfo(
                cluster=label,
                size=size,
                terms=terms.get(label, []),
                cohesion=float(sims[members].mean()),
                medoids=[units[int(i)].id for i in best],
                parts=int(len(np.unique(micro.labels_[members]))),
            )
        )
    write_jsonl(out / "clusters.jsonl.gz", infos)
    write_jsonl(
        out / "members.jsonl.gz",
        (
            Member(id=unit.id, cluster=int(labels[i]), sim=float(sims[i]))
            for i, unit in enumerate(units)
        ),
    )
    ami, sample = stability(matrix, labels, config)
    metrics = RunMetrics(
        units=len(units),
        clusters=len(infos),
        micro=int(micro.n_clusters),
        small_share=float(
            sum(i.size for i in infos if i.size < config.min_cluster_size) / len(units)
        ),
        mean_cohesion=float(sims.mean()),
        stability_ami=ami,
        stability_sample=sample,
    )
    (out / "metrics.json").write_text(metrics.model_dump_json(indent=2))
    return metrics
