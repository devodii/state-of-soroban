import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from state_of_soroban.github.client import GithubUnavailable
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

BATCH = 40
CONCURRENCY = 6
VALID_NAME = re.compile(r"^[\w.-]+/[\w.-]+$")
FIELDS = """
  nameWithOwner url description stargazerCount forkCount isFork isArchived isTemplate
  createdAt pushedAt homepageUrl diskUsage
  watchers {{ totalCount }}
  issues(states: OPEN) {{ totalCount }}
  parent {{ nameWithOwner }}
  primaryLanguage {{ name }}
  languages(first: 12, orderBy: {{field: SIZE, direction: DESC}}) {{ edges {{ size node {{ name }} }} }}
  licenseInfo {{ spdxId }}
  defaultBranchRef {{
    name
    target {{ ... on Commit {{
      oid
    }} }}
  }}
  owner {{ __typename login ... on User {{ location }} ... on Organization {{ location }} }}
  repositoryTopics(first: 25) {{ nodes {{ topic {{ name }} }} }}
"""


class Meta(BaseModel):
    full_name: str
    url: str
    owner: str
    owner_type: str
    owner_location: str | None
    description: str | None
    homepage: str | None
    topics: list[str] = Field(default_factory=list)
    language: str | None
    languages: dict[str, int] = Field(default_factory=dict)
    license: str | None
    stars: int
    forks: int
    watchers: int
    open_issues: int
    size_kb: int
    default_branch: str | None
    archived: bool
    is_fork: bool
    parent_full_name: str | None
    is_template: bool
    created_at: datetime | None
    pushed_at: datetime | None
    window_commits: int | None
    total_commits: int | None
    head_sha: str | None

    @classmethod
    def from_node(cls, node: dict[str, Any]) -> "Meta":
        branch = node["defaultBranchRef"]
        commit = (branch or {}).get("target") or {}
        return cls(
            full_name=node["nameWithOwner"],
            url=node["url"],
            owner=node["owner"]["login"],
            owner_type=node["owner"]["__typename"],
            owner_location=node["owner"].get("location"),
            description=node["description"],
            homepage=node["homepageUrl"] or None,
            topics=[e["topic"]["name"] for e in node["repositoryTopics"]["nodes"]],
            language=(node["primaryLanguage"] or {}).get("name"),
            languages={
                e["node"]["name"]: e["size"] for e in node["languages"]["edges"]
            },
            license=(node["licenseInfo"] or {}).get("spdxId"),
            stars=node["stargazerCount"],
            forks=node["forkCount"],
            watchers=node["watchers"]["totalCount"],
            open_issues=node["issues"]["totalCount"],
            size_kb=node["diskUsage"] or 0,
            default_branch=branch["name"] if branch else None,
            archived=node["isArchived"],
            is_fork=node["isFork"],
            parent_full_name=(node["parent"] or {}).get("nameWithOwner"),
            is_template=node["isTemplate"],
            created_at=node["createdAt"],
            pushed_at=node["pushedAt"],
            window_commits=commit.get("inWindow", {}).get("totalCount"),
            total_commits=commit.get("total", {}).get("totalCount"),
            head_sha=commit.get("oid"),
        )

    def row(self) -> tuple:
        return (
            self.full_name,
            self.url,
            self.owner,
            self.owner_type,
            self.owner_location,
            self.description,
            self.homepage,
            self.topics,
            self.language,
            self.languages,
            self.license,
            self.stars,
            self.forks,
            self.watchers,
            self.open_issues,
            self.size_kb,
            self.default_branch,
            self.archived,
            self.is_fork,
            self.parent_full_name,
            self.is_template,
            self.created_at,
            self.pushed_at,
            self.window_commits,
            self.total_commits,
            self.head_sha,
        )


def lookup(index: int, name: str, fields: str) -> str:
    owner, repo = name.split("/")
    return (
        f"r{index}: repository(owner: {json.dumps(owner)}, "
        f"name: {json.dumps(repo)}) {{{fields}}}"
    )


async def fetch_batch(context: Context, names: list[str]) -> dict[str, Meta | None]:
    window = context.workflow.window
    fields = FIELDS.format(start=window.start.isoformat(), end=window.end.isoformat())
    query = (
        "query {"
        + " ".join(lookup(i, name, fields) for i, name in enumerate(names))
        + "}"
    )
    try:
        data = await context.github.graphql(query)
    except GithubUnavailable:
        if len(names) == 1:
            context.errors += 1
            return {}
        half = len(names) // 2
        first = await fetch_batch(context, names[:half])
        second = await fetch_batch(context, names[half:])
        return {**first, **second}
    return {
        name: (Meta.from_node(data[f"r{i}"]) if data.get(f"r{i}") else None)
        for i, name in enumerate(names)
    }


@stage("github.metadata")
async def metadata(context: Context, _: Stage) -> None:
    async with context.pool.acquire() as connection:
        names = [
            row["full_name"]
            for row in await connection.fetch(
                load_sql("metadata_names"),
                context.force,
                context.workflow.autopilot.metadata_run_size,
            )
            if VALID_NAME.match(row["full_name"])
        ]
    if context.limit:
        names = names[: context.limit]
    batches = [names[i : i + BATCH] for i in range(0, len(names), BATCH)]
    gate = asyncio.Semaphore(CONCURRENCY)
    gone = 0

    async def one(batch: list[str]) -> None:
        nonlocal gone
        async with gate:
            found = await fetch_batch(context, batch)
        async with context.pool.acquire() as connection, connection.transaction():
            for asked, meta in found.items():
                if meta is None:
                    await connection.execute(
                        "DELETE FROM repos WHERE full_name = $1", asked
                    )
                    gone += 1
                    continue
                await connection.execute(load_sql("update_metadata"), *meta.row())
                if meta.full_name != asked:
                    await connection.execute(
                        load_sql("merge_stub"), asked, meta.full_name
                    )
                    await connection.execute(
                        "DELETE FROM repos WHERE full_name = $1", asked
                    )
        context.items += len(found)
        log.info("metadata for %s/%s repos", context.items, len(names))

    await asyncio.gather(*(one(batch) for batch in batches))
    context.detail["gone"] = gone
