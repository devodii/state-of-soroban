import re
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from state_of_soroban.config import get_settings

Network = Literal["mainnet", "testnet", "futurenet"]


class Window(BaseModel):
    start: date
    end: date

    @field_validator("end", mode="before")
    @classmethod
    def resolve_today(cls, value: object) -> object:
        return datetime.now(UTC).date() if value == "today" else value

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment.date() <= self.end


class CatalogFiles(BaseModel):
    patterns: Path | None = None
    bug_classes: Path


class CratesIo(BaseModel):
    crates: list[str]
    reverse_dependencies: bool = True


class DependentsSource(BaseModel):
    repo: str
    packages: list[str] = []


class Discover(BaseModel):
    crates_io: CratesIo
    repository_queries: list[str]
    code_queries: list[str]
    dependents: list[DependentsSource] = []
    exclude_owners: list[str] = []
    exclude_repos: list[str] = []
    min_window_commits: int = 0


class Clone(BaseModel):
    shallow_since: str
    max_repo_kb: int
    concurrency: int
    keep: bool = False
    keep_test_content: bool = False
    include_forks: bool = False
    require_language: str | None = None
    max_rust_files: int = 4000
    max_signal_files: int = 1500
    signal_suffixes: list[str]
    rust_suffixes: list[str]
    manifests: list[str]
    max_file_bytes: int
    skip_directories: list[str]


class DocumentKind(BaseModel):
    globs: list[str]


class Documents(BaseModel):
    max_text_bytes: int
    kinds: dict[str, DocumentKind]


class History(BaseModel):
    commits: Literal["all", "fixes", "none"] = "all"
    commit_files: bool = True
    issues: Literal["all", "bugs", "none"] = "all"
    releases: bool = True
    contributors: bool = True
    profiles: bool = True
    fix_message: str

    @field_validator("fix_message")
    @classmethod
    def compiles(cls, value: str) -> str:
        re.compile(value)
        return value


class NetworkSignal(BaseModel):
    signal: str
    regex: str

    @field_validator("regex")
    @classmethod
    def compiles(cls, value: str) -> str:
        re.compile(value)
        return value


class Expand(BaseModel):
    fork_pages: int = 10
    contributor_pages: int = 3
    min_contributor_repos: int = 2
    concurrency: int = 6


class Evidence(BaseModel):
    min_shared: int = 3
    min_overlap: float = 0.5


class Analysis(BaseModel):
    shards: int = 20
    embed_model: str = "BAAI/bge-small-en-v1.5"
    text_chars: int = 360
    clusters: int = 2500
    merge_distance: float = 0.3
    min_cluster_size: int = 25
    stability_sample: float = 0.3
    rerun_growth: float = 0.1
    max_run_hours: int = 6
    max_failures: int = 3
    retry_hours: int = 6
    terms: int = 8
    medoids: int = 6
    stop_words: list[str] = Field(default_factory=list)


class Web(BaseModel):
    port: int = 8080
    page_size: int = 50
    repo_sorts: list[str]


class Autopilot(BaseModel):
    followed: dict[str, str]
    periodic: list[str]
    periodic_seconds: int = 600
    discovery_seconds: int = 3600
    dependents_seconds: int = 21600
    pool_size: int = 40
    min_free_gb: int = 3
    download_concurrency: int = 12
    stats_seconds: int = 300
    metadata_run_size: int = 4000


class Readiness(BaseModel):
    min_recall: float = 0.99
    quiet_hours: int = 24
    max_new_soroban_in_quiet: int = 0
    min_known_rediscovered: float = 0.99
    known_file: Path | None = None


class Stage(BaseModel):
    id: str
    uses: str
    needs: list[str] = Field(default_factory=list)
    options: dict[str, object] = Field(default_factory=dict, alias="with")


class Workflow(BaseModel):
    name: str
    summary: str
    window: Window
    networks: list[Network]
    catalog: CatalogFiles
    discover: Discover
    clone: Clone
    expansion: Expand = Field(default_factory=Expand)
    documents: Documents
    history: History
    networks_signals: dict[Network, list[NetworkSignal]]
    autopilot: Autopilot
    web: Web
    evidence: Evidence = Field(default_factory=Evidence)
    analysis: Analysis = Field(default_factory=Analysis)
    readiness: Readiness = Field(default_factory=Readiness)
    stages: list[Stage]
    root: Path = Path(".")

    @model_validator(mode="after")
    def stages_are_wired(self) -> "Workflow":
        ids = [stage.id for stage in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError("stage ids must be unique")
        for stage in self.stages:
            for need in stage.needs:
                if need not in ids:
                    raise ValueError(f"{stage.id} needs unknown stage {need}")
        return self

    def expand(self, text: str) -> str:
        return text.replace("{start}", self.window.start.isoformat()).replace(
            "{end}", self.window.end.isoformat()
        )

    def catalog_path(self, name: str) -> Path:
        return self.root / getattr(self.catalog, name)


@lru_cache
def load_workflow(path: Path | None = None) -> Workflow:
    file = path or get_settings().workflow_file
    raw = yaml.safe_load(file.read_text())
    return Workflow(**raw, root=file.parent)
