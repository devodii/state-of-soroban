import logging
import math
import re

from state_of_soroban.extract.rust import digest
from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.stages.gaps import gap_report
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

SPECIFICITY_CAP = 0.2
WORD = re.compile(r"[a-z][a-z0-9\-]{2,}")
STOP = set(
    """the and for with from that this when into have has had are was were been being not but can could should would
    will you your our their its any all some more most other than then they them what which who how why where
    use used using get got set let new old fix fixed add added adds remove removed update updated bug error issue
    pull request feature please help does doesn make made like also just still only need needs want same one two""".split()
)


def ratio(part: float, whole: float) -> float:
    return min(1.0, part / whole) if whole else 0.0


def tokenise(title: str) -> list[str]:
    return [w for w in WORD.findall(title.lower()) if w not in STOP]


async def collect_evidence(context: Context, need) -> dict[str, int]:
    cfg = context.workflow.improve.needs
    signals = need["signals"] or {}
    pool = context.pool
    rows: list[tuple] = []
    counts: dict[str, int] = {}
    query = need["query"]
    if query:
        for row in await pool.fetch(
            load_sql("need_issues"), query, cfg.evidence_per_kind, cfg.min_relevance
        ):
            rows.append(
                (
                    need["id"],
                    row["kind"],
                    row["repo"],
                    row["ref"],
                    row["relevance"],
                    row["title"],
                    row["snippet"],
                    row["url"],
                    row["created_at"],
                )
            )
        for row in await pool.fetch(
            load_sql("need_documents"), query, cfg.evidence_per_kind, cfg.min_relevance
        ):
            rows.append(
                (
                    need["id"],
                    "document",
                    row["repo"],
                    row["ref"],
                    row["relevance"],
                    f"{row['kind']}: {row['title']}",
                    row["snippet"],
                    row["url"],
                    None,
                )
            )
        for row in await pool.fetch(
            load_sql("need_repos"), query, cfg.evidence_per_kind
        ):
            if row["relevance"] >= cfg.min_relevance:
                rows.append(
                    (
                        need["id"],
                        "repo",
                        row["repo"],
                        row["ref"],
                        row["relevance"],
                        row["title"],
                        row["snippet"],
                        row["url"],
                        None,
                    )
                )
    dependencies = [d.lower() for d in signals.get("dependencies", [])]
    if dependencies:
        for row in await pool.fetch(load_sql("need_dependencies"), dependencies, 150):
            rows.append(
                (
                    need["id"],
                    "dependency",
                    row["repo"],
                    row["ref"],
                    1.0,
                    row["title"],
                    row["snippet"],
                    row["url"],
                    None,
                )
            )
    if query:
        for row in await pool.fetch(
            load_sql("need_questions"), query, cfg.evidence_per_kind, cfg.min_issue_rank
        ):
            rows.append(
                (
                    need["id"],
                    "question",
                    row["repo"],
                    row["ref"],
                    row["relevance"],
                    row["title"],
                    row["snippet"],
                    row["url"],
                    row["created_at"],
                )
            )
    for pattern in signals.get("paths", []):
        for row in await pool.fetch(load_sql("need_paths"), pattern, 100):
            rows.append(
                (
                    need["id"],
                    "path",
                    row["repo"],
                    row["ref"],
                    1.0,
                    row["title"],
                    row["snippet"],
                    row["url"],
                    None,
                )
            )
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(load_sql("clear_need_evidence"), need["id"])
        await connection.executemany(load_sql("ins_need_evidence"), rows)
    for row in rows:
        counts[row[1]] = counts.get(row[1], 0) + 1
    return counts


def coverage(tools: list) -> float:
    weight = {"covers": 1.0, "partial": 0.35, "adjacent": 0.1}
    return min(1.0, sum(weight.get(t["relation"], 0) for t in tools))


def percentile(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.values())
    if not ordered:
        return {}
    last = max(len(ordered) - 1, 1)
    return {
        key: sum(1 for v in ordered if v < value) / last
        + sum(1 for v in ordered if v == value) / (2 * max(len(ordered), 1))
        for key, value in values.items()
    }


async def measure_need(context: Context, need, counts: dict) -> dict:
    cfg = context.workflow.improve.needs
    pool = context.pool
    signals = need["signals"] or {}
    paths = "|".join(f"({p})" for p in signals.get("paths", [])) or "^$never^"
    cue = "|".join(re.escape(c) for c in cfg.cue_words) or "^$never^"
    m = dict(
        await pool.fetchrow(
            load_sql("need_stats"),
            need["query"] or "",
            [d.lower() for d in signals.get("dependencies", [])],
            paths,
            context.catalog.official_owners,
            context.workflow.improve.score.recent_days,
            cfg.min_issue_rank,
            cfg.min_doc_rank,
            cue,
            cfg.noise_title,
        )
    )
    relevance = await pool.fetchval(load_sql("need_relevance"), need["id"])
    tools = [dict(t) for t in await pool.fetch(load_sql("need_tools_for"), need["id"])]
    share = m["issues"] / max(m["corpus_issues"], 1)
    return {
        "need": need,
        "m": m,
        "tools": tools,
        "relevance": float(relevance or 0),
        "share": share,
        "counts": counts,
    }


async def finalise(
    context: Context, measured: list[dict], totals: tuple[int, int]
) -> None:
    cfg = context.workflow.improve.needs
    pool = context.pool
    weights = cfg.weights.model_dump()
    positive = sum(w for w in weights.values() if w > 0)
    raw_signals = {
        "pain": {
            d["need"]["id"]: math.log1p(d["m"]["pain_owners"])
            + 0.3 * math.log1p(d["m"]["pain_issues"])
            for d in measured
        },
        "owners": {d["need"]["id"]: float(d["m"]["owners"]) for d in measured},
        "relevance": {d["need"]["id"]: d["relevance"] for d in measured},
        "official": {d["need"]["id"]: float(d["m"]["official"]) for d in measured},
        "custom": {d["need"]["id"]: float(d["m"]["custom_repos"]) for d in measured},
        "recency": {
            d["need"]["id"]: ratio(d["m"]["recent"], d["m"]["dated"]) for d in measured
        },
        "engagement": {d["need"]["id"]: float(d["m"]["engagement"]) for d in measured},
    }
    ranks = {name: percentile(values) for name, values in raw_signals.items()}
    for data in measured:
        need, m, tools = data["need"], data["m"], data["tools"]
        key = need["id"]
        components = {name: ranks[name][key] for name in raw_signals}
        components["covered"] = coverage(tools)
        specificity = 1 - min(1.0, data["share"] / SPECIFICITY_CAP)
        raw = max(
            0.0, 100 * sum(weights[k] * v for k, v in components.items()) / positive
        )
        total = raw * (0.4 + 0.6 * specificity)
        segments = [dict(r) for r in await pool.fetch(load_sql("need_segments"), key)]
        top = [dict(r) for r in await pool.fetch(load_sql("need_top_evidence"), key, 6)]
        for item in top:
            item["relevance"] = round(float(item["relevance"]), 3)
        metrics = {k: int(v) for k, v in m.items()}
        metrics["match_share_of_issues"] = round(data["share"], 4)
        metrics["specificity"] = round(specificity, 3)
        problem = (
            f"{need['summary']} Evidence in the corpus: {m['pain_issues']} issues voice this as a problem or request "
            f"from {m['pain_owners']} different owners ({m['issues']} topical issues in all, {m['open_issues']} open), "
            f"{m['documents']} documents mention it and {m['custom_repos']} repos already carry their own implementation."
        )
        gap = (
            "No existing tool is recorded for this need."
            if not tools
            else "Partly served by "
            + ", ".join(f"{t['name']} ({t['relation']})" for t in tools)
            + ". The evidence shows developers still build their own, so the gap is what these do not cover."
        )
        analysed_gap, analysis = await gap_report(context.pool, key)
        gap = analysed_gap or gap
        seed = next((n for n in context.catalog.needs if n.id == key), None)
        detail = {
            "components": {k: round(v, 4) for k, v in components.items()},
            "evidence_rows": data["counts"],
            "raw_score": round(raw, 2),
            "scoring": "each signal is a percentile among all needs, weighted, then scaled by specificity",
        }
        rfp = {
            "title": need["title"],
            "problem": problem,
            "gap": gap,
            "gap_analysis": analysis,
            "who_is_affected": segments,
            "existing_tools": tools,
            "evidence_highlights": top,
            "deliverables": seed.deliverables if seed else [],
            "success_metrics": seed.success if seed else [],
            "demand": metrics,
            "priority": "high" if total >= 60 else "medium" if total >= 40 else "low",
        }
        await pool.execute(
            load_sql("update_need_score"), key, round(total, 2), metrics, detail, rfp
        )


async def mine_needs(context: Context) -> int:
    cfg = context.workflow.improve.needs
    rows = await context.pool.fetch(load_sql("mine_need_titles"))
    cues = [c.lower() for c in cfg.cue_words]
    owners_by_gram: dict[str, set[str]] = {}
    example: dict[str, str] = {}
    for row in rows:
        title = row["title"] or ""
        lowered = title.lower()
        if not any(c in lowered for c in cues) or re.match(
            cfg.noise_title, title, re.I
        ):
            continue
        words = tokenise(title)
        seen = set()
        for n in (2, 3):
            for i in range(len(words) - n + 1):
                gram = " ".join(words[i : i + n])
                if gram in seen:
                    continue
                seen.add(gram)
                owners_by_gram.setdefault(gram, set()).add(row["owner"])
                example.setdefault(gram, title)
    seed_queries = [n.query for n in context.catalog.needs]
    ranked = sorted(
        (
            (g, len(o))
            for g, o in owners_by_gram.items()
            if len(o) >= cfg.min_ngram_owners
        ),
        key=lambda x: (-x[1], -len(x[0])),
    )
    made = 0
    taken: list[str] = []
    for gram, owners in ranked:
        if any(gram in t or t in gram for t in taken):
            continue
        covered = await context.pool.fetchval(
            "SELECT bool_or(to_tsvector('english', $1) @@ websearch_to_tsquery('english', q)) FROM unnest($2::text[]) AS q",
            gram,
            seed_queries,
        )
        if covered:
            continue
        taken.append(gram)
        await context.pool.execute(
            load_sql("upsert_mined_need"),
            f"mined-{digest(gram)}",
            f"Recurring request: {gram}",
            f'{owners} different owners filed requests mentioning "{gram}". Example: {example[gram][:160]}',
            f'"{gram}"',
        )
        made += 1
        if made >= cfg.top_mined:
            break
    return made


@stage("catalog.needs")
async def needs(context: Context, _: Stage) -> None:
    mined = await mine_needs(context)
    totals_row = await context.pool.fetchrow(load_sql("need_totals"))
    totals = (max(totals_row["owners"], 2), max(totals_row["repos"], 1))
    listing = [dict(r) for r in await context.pool.fetch(load_sql("list_needs"))]
    measured = []
    for need in listing:
        counts = await collect_evidence(context, need)
        measured.append(await measure_need(context, need, counts))
        context.items += 1
    await finalise(context, measured, totals)
    await context.pool.execute(
        "DELETE FROM tooling_needs WHERE origin = 'mined' AND scored_at IS NULL"
    )
    context.detail.update({"needs": len(listing), "mined_new": mined})
    log.info("needs: %s scored, %s mined phrases", len(listing), mined)
