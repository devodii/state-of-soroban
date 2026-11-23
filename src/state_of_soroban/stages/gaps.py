import json
import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field

from state_of_soroban.catalog import Need, Tool
from state_of_soroban.runner import Context, stage
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

STALE_DAYS = 365
ACTIVE_DAYS = 120
COVERED = 0.6
PARTLY = 0.3
STOPWORDS = frozenset(
    "a an and are as at be by for from in into is it of on or per the their to "
    "with without across all any each every more most other over under using use "
    "one two same these those this that than then them they your our out new "
    "soroban stellar contract contracts support tool tools tooling library libraries "
    "project projects developer developers build make work get set ensure provide".split()
)
GITHUB_URL = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)")
FIELDS = """
pushedAt isArchived stargazerCount description
openIssues: issues(states: OPEN) { totalCount }
readme: object(expression: "HEAD:README.md") { ... on Blob { text } }
root: object(expression: "HEAD:") { ... on Tree { entries { name type } } }
docs: object(expression: "HEAD:docs") { ... on Tree { entries { name type } } }
issues(states: OPEN, first: 100, orderBy: {field: COMMENTS, direction: DESC}) {
  nodes { number title url bodyText createdAt reactions { totalCount } comments { totalCount } }
}
pullRequests(states: MERGED, first: 40, orderBy: {field: UPDATED_AT, direction: DESC}) {
  nodes { mergedAt }
}
releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { tagName publishedAt } }
"""


class Request(BaseModel):
    title: str
    url: str
    reactions: int
    comments: int
    score: float


class Snapshot(BaseModel):
    repo: str
    pushed_at: datetime | None = None
    archived: bool = False
    stars: int = 0
    open_issues: int = 0
    merged_prs_180d: int = 0
    last_release_at: datetime | None = None
    text: str = ""
    entries: list[str] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)


class Item(BaseModel):
    index: int
    text: str
    status: str
    coverage: Decimal
    evidence: list[Request | dict] = Field(default_factory=list)


def terms(text: str) -> set[str]:
    found = set()
    for word in re.findall(r"[a-z][a-z0-9+#-]{1,}", text.lower()):
        if word in STOPWORDS:
            continue
        for suffix in ("ing", "ers", "er", "es", "ed", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)]
                break
        found.add(word)
    return found


def moment(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def parse(repo: str, node: dict) -> Snapshot:
    cutoff = datetime.now(UTC) - timedelta(days=180)
    merged = [
        n["mergedAt"]
        for n in (node.get("pullRequests") or {}).get("nodes", [])
        if n.get("mergedAt")
        and datetime.fromisoformat(n["mergedAt"].replace("Z", "+00:00")) >= cutoff
    ]
    entries = [
        e["name"]
        for key in ("root", "docs")
        for e in ((node.get(key) or {}).get("entries") or [])
    ]
    releases = (node.get("releases") or {}).get("nodes") or []
    pushed = node.get("pushedAt")
    return Snapshot(
        repo=repo,
        pushed_at=moment(pushed),
        archived=bool(node.get("isArchived")),
        stars=node.get("stargazerCount") or 0,
        open_issues=(node.get("openIssues") or {}).get("totalCount", 0),
        merged_prs_180d=len(merged),
        last_release_at=moment(releases[0].get("publishedAt")) if releases else None,
        text=" ".join(
            [
                node.get("description") or "",
                (node.get("readme") or {}).get("text") or "",
            ]
        ),
        entries=entries,
        issues=(node.get("issues") or {}).get("nodes", []),
    )


def judge(item_text: str, snapshot: Snapshot, index: int) -> Item:
    wanted = terms(item_text)
    if not wanted:
        return Item(index=index, text=item_text, status="unknown", coverage=Decimal(0))
    have = terms(snapshot.text) | terms(" ".join(snapshot.entries))
    coverage = len(wanted & have) / len(wanted)
    asked: list[Request] = []
    for issue in snapshot.issues:
        issue_terms = terms(f"{issue['title']} {(issue.get('bodyText') or '')[:1500]}")
        title_terms = terms(issue["title"])
        hit = len(wanted & issue_terms) / len(wanted)
        shared = wanted & issue_terms
        if hit >= 0.5 and len(shared) >= 2 and wanted & title_terms:
            asked.append(
                Request(
                    title=issue["title"],
                    url=issue["url"],
                    reactions=issue["reactions"]["totalCount"],
                    comments=issue["comments"]["totalCount"],
                    score=round(hit, 2),
                )
            )
    asked.sort(key=lambda r: (-r.reactions - r.comments, -r.score))
    if coverage >= COVERED:
        status = "covered"
    elif asked:
        status = "related"
    elif coverage >= PARTLY:
        status = "partly"
    else:
        status = "missing"
    return Item(
        index=index,
        text=item_text,
        status=status,
        coverage=Decimal(f"{coverage:.2f}"),
        evidence=asked[:3],
    )


def verdict(tool: Tool, snapshot: Snapshot | None, items: list[Item]) -> dict:
    if snapshot is None:
        return {
            "verdict": "unverified",
            "summary": f"{tool.name} is a hosted service or has no public repository, so what it lacks cannot be read from code; the missing items below come from the need itself.",
            "reasons": ["no public repository to inspect"],
        }
    now = datetime.now(UTC)
    missing = [i for i in items if i.status in ("missing", "related", "partly")]
    asked = [i for i in items if i.status == "related"]
    days = (now - snapshot.pushed_at).days if snapshot.pushed_at else 9999
    reasons = []
    if snapshot.archived:
        reasons.append("the repository is archived")
    if days > STALE_DAYS:
        reasons.append(f"no push for {days} days")
    if reasons:
        return {
            "verdict": "build-new",
            "summary": f"{tool.name} is not maintained ({'; '.join(reasons)}), so the missing pieces need a new tool.",
            "reasons": reasons,
        }
    active = days <= ACTIVE_DAYS and snapshot.merged_prs_180d >= 3
    reasons = [
        f"last push {days} days ago",
        f"{snapshot.merged_prs_180d} pull requests merged in 180 days",
    ]
    if asked:
        reasons.append(f"{len(asked)} missing items have related open issues upstream")
    share = len(missing) / len(items) if items else 0
    if share >= 0.75 and not asked:
        return {
            "verdict": "review",
            "summary": f"{tool.name} is maintained and its README, docs index and open issues never mention {len(missing)} of the {len(items)} needed capabilities. Open an upstream issue to ask whether they are in scope: a yes means contribute, a no means build new.",
            "reasons": reasons,
        }
    if active or asked:
        return {
            "verdict": "contribute",
            "summary": f"{tool.name} is actively maintained and has related open issues for {len(asked)} of the {len(missing)} missing items, so contribute upstream.",
            "reasons": reasons,
        }
    return {
        "verdict": "contribute",
        "summary": f"{tool.name} is maintained but quiet; propose the {len(missing)} missing items upstream first and build separately if they decline.",
        "reasons": reasons,
    }


def repos_of(tool: Tool) -> list[str]:
    match = tool.url and GITHUB_URL.search(tool.url)
    first = [f"{match.group(1)}/{match.group(2)}"] if match else []
    return list(dict.fromkeys([*first, *tool.repos]))


def merge(repo: str, parts: list[Snapshot]) -> Snapshot | None:
    if not parts:
        return None
    pushed = [p.pushed_at for p in parts if p.pushed_at]
    released = [p.last_release_at for p in parts if p.last_release_at]
    return Snapshot(
        repo=repo,
        pushed_at=max(pushed) if pushed else None,
        archived=all(p.archived for p in parts),
        stars=sum(p.stars for p in parts),
        open_issues=sum(p.open_issues for p in parts),
        merged_prs_180d=sum(p.merged_prs_180d for p in parts),
        last_release_at=max(released) if released else None,
        text=" ".join(p.text for p in parts),
        entries=[e for p in parts for e in p.entries],
        issues=[i for p in parts for i in p.issues],
    )


async def fetch(context: Context, repos: list[str]) -> dict[str, Snapshot]:
    found: dict[str, Snapshot] = {}
    for repo in repos:
        owner, name = repo.split("/")
        query = (
            f"query {{ repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
            f"{{ {FIELDS} }} }}"
        )
        try:
            data = await context.github.graphql(query)
        except Exception as error:
            log.warning("could not read %s: %s", repo, str(error)[:120])
            context.errors += 1
            continue
        if data.get("repository"):
            found[repo] = parse(repo, data["repository"])
    return found


async def analyse(context: Context, need: Need, tool: Tool, snapshot: Snapshot | None):
    items = [
        judge(text, snapshot, index)
        if snapshot
        else Item(index=index, text=text, status="unknown", coverage=Decimal(0))
        for index, text in enumerate(need.deliverables)
    ]
    result = verdict(tool, snapshot, items)
    async with context.pool.acquire() as connection, connection.transaction():
        await connection.execute(
            "DELETE FROM need_tool_gaps WHERE need = $1 AND tool = $2", need.id, tool.id
        )
        await connection.executemany(
            "INSERT INTO need_tool_gaps (need, tool, item_index, item, status, coverage, evidence) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)",
            [
                (
                    need.id,
                    tool.id,
                    i.index,
                    i.text,
                    i.status,
                    i.coverage,
                    [
                        e.model_dump(mode="json") if isinstance(e, BaseModel) else e
                        for e in i.evidence
                    ],
                )
                for i in items
            ],
        )
        await connection.execute(
            "INSERT INTO need_tool_verdicts (need, tool, verdict, summary, reasons, missing, requested, covered) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
            "ON CONFLICT (need, tool) DO UPDATE SET verdict = EXCLUDED.verdict, "
            "summary = EXCLUDED.summary, reasons = EXCLUDED.reasons, missing = EXCLUDED.missing, "
            "requested = EXCLUDED.requested, covered = EXCLUDED.covered, scored_at = now()",
            need.id,
            tool.id,
            result["verdict"],
            result["summary"],
            result["reasons"],
            sum(i.status in ("missing", "partly", "related") for i in items),
            sum(i.status == "related" for i in items),
            sum(i.status == "covered" for i in items),
        )
    context.items += 1


@stage("catalog.gaps")
async def gaps(context: Context, _: Stage) -> None:
    tools = {t.id: t for t in context.catalog.tools}
    pairs = [
        (need, tools[link.id])
        for need in context.catalog.needs
        for link in need.tools
        if link.relation == "partial" and link.id in tools
    ]
    repos = sorted({r for _, t in pairs for r in repos_of(t)})
    snapshots = await fetch(context, repos)
    combined: dict[str, Snapshot | None] = {}
    for tool in {t.id: t for _, t in pairs}.values():
        wanted = repos_of(tool)
        found = [snapshots[r] for r in wanted if r in snapshots]
        for repo in wanted:
            if repo not in snapshots:
                log.warning("%s: repository %s was not found", tool.id, repo)
        combined[tool.id] = merge(wanted[0], found) if wanted else None
        snapshot = combined[tool.id]
        if snapshot:
            await context.pool.execute(
                "INSERT INTO tool_snapshots (tool, repo, pushed_at, archived, stars, open_issues, "
                "merged_prs_180d, last_release_at, data) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb) "
                "ON CONFLICT (tool) DO UPDATE SET repo = EXCLUDED.repo, fetched_at = now(), "
                "pushed_at = EXCLUDED.pushed_at, archived = EXCLUDED.archived, stars = EXCLUDED.stars, "
                "open_issues = EXCLUDED.open_issues, merged_prs_180d = EXCLUDED.merged_prs_180d, "
                "last_release_at = EXCLUDED.last_release_at, data = EXCLUDED.data",
                tool.id,
                ", ".join(wanted),
                snapshot.pushed_at,
                snapshot.archived,
                snapshot.stars,
                snapshot.open_issues,
                snapshot.merged_prs_180d,
                snapshot.last_release_at,
                snapshot.model_dump(mode="json", exclude={"text"}, exclude_none=True),
            )
    for need, tool in pairs:
        await analyse(context, need, tool, combined[tool.id])
    for need_id in sorted({need.id for need, _ in pairs}):
        text, report = await gap_report(context.pool, need_id)
        await context.pool.execute(
            "UPDATE tooling_needs SET rfp = rfp || jsonb_build_object('gap', $2::text, 'gap_analysis', $3::jsonb) "
            "WHERE id = $1",
            need_id,
            text,
            report,
        )
    log.info("gaps: %s need and tool pairs analysed", len(pairs))


VERDICT_LABEL = {
    "contribute": "contribute upstream",
    "build-new": "build a new tool",
    "review": "ask upstream, then decide",
    "unverified": "hosted or closed, not inspectable",
}


async def gap_report(pool, need_id: str) -> tuple[str, list[dict]]:
    verdicts = await pool.fetch(
        "SELECT v.tool, t.name, t.url, v.verdict, v.summary, v.reasons "
        "FROM need_tool_verdicts AS v INNER JOIN tool_catalog AS t ON v.tool = t.id "
        "WHERE v.need = $1 ORDER BY v.tool",
        need_id,
    )
    report = []
    for row in verdicts:
        items = await pool.fetch(
            "SELECT item, status, coverage, evidence FROM need_tool_gaps "
            "WHERE need = $1 AND tool = $2 ORDER BY item_index",
            need_id,
            row["tool"],
        )
        report.append(
            {
                "tool": row["tool"],
                "name": row["name"],
                "url": row["url"],
                "verdict": row["verdict"],
                "summary": row["summary"],
                "reasons": list(row["reasons"]),
                "items": [
                    {
                        "item": i["item"],
                        "status": i["status"],
                        "coverage": float(i["coverage"]),
                        "evidence": i["evidence"],
                    }
                    for i in items
                ],
            }
        )
    if not report:
        return "", []
    lines = []
    for tool in report:
        missing = [i for i in tool["items"] if i["status"] != "covered"]
        asked = [i for i in missing if i["evidence"]]
        text = f"{tool['name']}: {VERDICT_LABEL[tool['verdict']]}. {tool['summary']}"
        if missing:
            text += " Missing: " + "; ".join(i["item"] for i in missing) + "."
        if asked:
            text += " Related open issues upstream: " + "; ".join(
                f"{i['evidence'][0]['title']} ({i['evidence'][0]['url']})"
                for i in asked
            )
        lines.append(text)
    return "\n\n".join(lines), report
