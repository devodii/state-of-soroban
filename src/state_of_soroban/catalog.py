import re
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from state_of_soroban.workflow import Workflow


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


class Catalog(BaseModel):
    patterns: list[Pattern]
    bug_classes: list[BugClass]


def load_catalog(workflow: Workflow) -> Catalog:
    def read(name: str, key: str) -> list[dict]:
        return yaml.safe_load(workflow.catalog_path(name).read_text())[key]

    return Catalog(
        patterns=read("patterns", "patterns") if workflow.catalog.patterns else [],
        bug_classes=read("bug_classes", "bug_classes"),
    )
