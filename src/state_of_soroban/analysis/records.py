import gzip
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel


class Unit(BaseModel):
    id: str
    text: str
    family: str
    owner: str


class Member(BaseModel):
    id: str
    cluster: int
    sim: float


class ClusterInfo(BaseModel):
    cluster: int
    size: int
    terms: list[str]
    cohesion: float
    medoids: list[str]
    parts: int


class RunMetrics(BaseModel):
    units: int
    clusters: int
    micro: int
    small_share: float
    mean_cohesion: float
    stability_ami: float
    stability_sample: int


def read_jsonl(path: Path, model: type[BaseModel]) -> Iterator:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            yield model.model_validate_json(line)


def write_jsonl(path: Path, items: Iterator[BaseModel] | list[BaseModel]) -> int:
    count = 0
    with gzip.open(path, "wt", encoding="utf-8") as target:
        for item in items:
            target.write(item.model_dump_json() + "\n")
            count += 1
    return count
