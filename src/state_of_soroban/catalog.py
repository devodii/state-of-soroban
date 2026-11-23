import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from state_of_soroban.workflow import Workflow

Role = Literal["boilerplate", "footgun", "adopted"]


class Match(BaseModel):
    kind: Literal["regex", "function", "type"]
    regex: str | None = None
    name: str | None = None
    contains: list[str] = Field(default_factory=list)
    lacks: list[str] = Field(default_factory=list)
    params_match: str | None = None
    max_loc: int | None = None
    contract_only: bool = False
    skip_tests: bool = False
    is_test_helper: bool = False
    type_kind: Literal["struct", "enum"] | None = None
    flags: list[str] = Field(default_factory=list)

    @field_validator("regex", "name", "params_match")
    @classmethod
    def compiles(cls, value: str | None) -> str | None:
        if value is not None:
            re.compile(value)
        return value

    @field_validator("contains", "lacks")
    @classmethod
    def all_compile(cls, values: list[str]) -> list[str]:
        for value in values:
            re.compile(value)
        return values


class Pattern(BaseModel):
    id: str
    category: str
    description: str
    match: Match
    diff: str | None = None

    @field_validator("diff")
    @classmethod
    def diff_compiles(cls, value: str | None) -> str | None:
        if value is not None:
            re.compile(value)
        return value


class BugClass(BaseModel):
    id: str
    name: str
    description: str
    severity: Literal["low", "medium", "high", "critical"]
    keywords: str

    @field_validator("keywords")
    @classmethod
    def compiles(cls, value: str) -> str:
        re.compile(value)
        return value


class Library(BaseModel):
    id: str
    name: str
    crates: list[str]
    owners: list[str] = Field(default_factory=list)
    solves: list[str] = Field(default_factory=list)


class Thresholds(BaseModel):
    min_repos: int
    min_share: float
    min_occurrences: int


class ProposalPattern(BaseModel):
    id: str
    role: Role


class Proposal(BaseModel):
    id: str
    name: str
    kind: str
    summary: str
    sketch: str | None = None
    thresholds: Thresholds
    covered_by: list[str] = Field(default_factory=list)
    patterns: list[ProposalPattern]
    bug_classes: list[str]


class Tool(BaseModel):
    id: str
    name: str
    category: str
    url: str | None = None
    description: str
    ecosystems: list[str] = Field(default_factory=list)
    packages: dict[str, list[str]] = Field(default_factory=dict)
    repos: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    solves: list[str] = Field(default_factory=list)


class NeedSignals(BaseModel):
    dependencies: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)

    @field_validator("paths")
    @classmethod
    def paths_compile(cls, values: list[str]) -> list[str]:
        for value in values:
            re.compile(value)
        return values


class NeedTool(BaseModel):
    id: str
    relation: Literal["covers", "partial", "adjacent"] = "partial"


class Need(BaseModel):
    id: str
    title: str
    category: str
    summary: str
    query: str
    signals: NeedSignals = Field(default_factory=NeedSignals)
    tools: list[NeedTool] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    success: list[str] = Field(default_factory=list)


class Catalog(BaseModel):
    patterns: list[Pattern]
    bug_classes: list[BugClass]
    libraries: list[Library]
    proposals: list[Proposal]
    tools: list[Tool] = Field(default_factory=list)
    needs: list[Need] = Field(default_factory=list)
    official_owners: list[str] = Field(default_factory=list)

    def pattern(self, pattern_id: str) -> Pattern:
        return next(p for p in self.patterns if p.id == pattern_id)

    def library_for_crate(self, crate: str) -> Library | None:
        return next((lib for lib in self.libraries if crate in lib.crates), None)

    def validate_links(self) -> None:
        patterns = {p.id for p in self.patterns}
        bugs = {b.id for b in self.bug_classes}
        libraries = {lib.id for lib in self.libraries}
        for proposal in self.proposals:
            for item in proposal.patterns:
                if item.id not in patterns:
                    raise ValueError(f"{proposal.id} uses unknown pattern {item.id}")
            for bug in proposal.bug_classes:
                if bug not in bugs:
                    raise ValueError(f"{proposal.id} maps to unknown bug class {bug}")
            for library in proposal.covered_by:
                if library not in libraries:
                    raise ValueError(f"{proposal.id} cites unknown library {library}")
        tools = {t.id for t in self.tools}
        needs = {n.id for n in self.needs}
        for need in self.needs:
            for link in need.tools:
                if link.id not in tools:
                    raise ValueError(f"{need.id} cites unknown tool {link.id}")
        for tool in self.tools:
            for solved in tool.solves:
                if solved not in needs:
                    raise ValueError(f"{tool.id} solves unknown need {solved}")


def load_catalog(workflow: Workflow) -> Catalog:
    def read(name: str, key: str) -> list[dict]:
        return yaml.safe_load(workflow.catalog_path(name).read_text())[key]

    needs_file = yaml.safe_load(workflow.catalog_path("needs").read_text())
    catalog = Catalog(
        patterns=read("patterns", "patterns"),
        bug_classes=read("bug_classes", "bug_classes"),
        libraries=read("libraries", "libraries"),
        proposals=read("proposals", "proposals"),
        tools=read("tools", "tools"),
        needs=needs_file["needs"],
        official_owners=needs_file.get("official_owners", []),
    )
    catalog.validate_links()
    return catalog


async def active_patterns(pool, catalog: Catalog) -> list[Pattern]:
    import json

    rows = await pool.fetch(
        "SELECT id, category, description, matcher, diff FROM patterns "
        "WHERE origin = 'mined' AND status = 'active' ORDER BY id"
    )
    mined = [
        Pattern(
            id=row["id"],
            category=row["category"],
            description=row["description"],
            match=Match(**json.loads(row["matcher"])),
            diff=row["diff"],
        )
        for row in rows
    ]
    return [*catalog.patterns, *mined]
