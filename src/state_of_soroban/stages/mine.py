import json
import logging
import re
from collections import Counter

from state_of_soroban.extract.rust import digest
from state_of_soroban.runner import Context, stage
from state_of_soroban.scoring import Metrics, score
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

WORD = re.compile(r"[a-z][a-z_]{3,}")
STOP = set(
    """this that with from have will into when then they them were been also just more only some
    than what which would should could about after before other make made does done update updated
    add added adds remove removed removes change changed changes fix fixed fixes merge merged branch
    pull request commit commits initial test tests testing contract contracts soroban stellar rust
    code file files readme docs doc version release""".split()
)
SNIPPET_LINES = 40


async def snippet(context: Context, repo: str, path: str, start: int, end: int) -> str:
    content = await context.pool.fetchval(load_sql("sample_source"), repo, path)
    if not content:
        return ""
    lines = content.splitlines()[max(start - 1, 0) : end][:SNIPPET_LINES]
    return "\n".join(lines)


async def totals(context: Context) -> tuple[int, int]:
    row = await context.pool.fetchrow(load_sql("ecosystem_totals"))
    return max(row["total_owners"], 2), max(row["total_repos"], 1)


async def member_pairs(context: Context, query: str, key: str) -> tuple[list, list]:
    rows = await context.pool.fetch(load_sql(query), key)
    return [r["repo"] for r in rows], [r["path"] for r in rows]


async def evaluate(
    context: Context,
    members: tuple[list, list],
    base: dict,
    owners: int,
    totals_: tuple[int, int],
) -> tuple[Metrics, dict]:
    libraries = [c for lib in context.catalog.libraries for c in lib.crates]
    row = await context.pool.fetchrow(
        load_sql("member_metrics"),
        members[0],
        members[1],
        context.workflow.improve.score.recent_days,
        libraries,
    )
    metrics = Metrics(
        **{k: row[k] for k in row.keys()},
        occurrences=base["occurrences"],
        bodies=base.get("bodies", base["occurrences"]),
        loc_total=int(base.get("loc_total") or 0),
        total_owners=totals_[0],
        total_repos=totals_[1],
    )
    metrics.owners = owners
    scored = score(metrics, context.workflow.improve.score.weights).model_dump()
    examples = await context.pool.fetch(
        load_sql("fix_examples"), members[0], members[1]
    )
    scored["fix_examples"] = [
        {
            "repo": e["repo"],
            "sha": e["sha"][:10],
            "message": e["message"][:140],
            "date": str(e["committed_at"])[:10],
        }
        for e in examples
    ]
    return metrics, scored


async def save(
    context: Context,
    kind: str,
    title: str,
    signature: str,
    metrics: Metrics,
    scored: dict,
    sample: dict,
    proposal_kind: str | None,
    extra: dict | None = None,
    members: list[str] | None = None,
) -> None:
    identifier = f"{kind}:{digest(signature)}"
    evidence = {
        "metrics": metrics.model_dump(),
        "components": scored["components"],
        "weighted": scored["weighted"],
        "copy_share": scored["copy_share"],
        "fix_examples": scored.get("fix_examples", []),
        "sample": sample,
        **(extra or {}),
    }
    await context.pool.execute(
        load_sql("upsert_candidate"),
        identifier,
        kind,
        title,
        signature,
        metrics.repos,
        metrics.occurrences,
        scored["score"],
        evidence,
        None,
    )
    if proposal_kind:
        thresholds = context.workflow.improve.mine
        await context.pool.execute(
            load_sql("upsert_mined_proposal"),
            f"mined-{identifier.replace(':', '-')}",
            title,
            proposal_kind,
            summarise(kind, metrics, scored),
            sample.get("snippet"),
            thresholds.min_owners,
            0,
            metrics.occurrences,
            scored["score"],
            evidence,
        )
        if members:
            proposal_id = f"mined-{identifier.replace(':', '-')}"
            await context.pool.execute(load_sql("clear_proposal_repos"), proposal_id)
            await context.pool.execute(
                load_sql("add_proposal_repos"), proposal_id, sorted(set(members))
            )


def summarise(kind: str, metrics: Metrics, scored: dict) -> str:
    independent = f"{round((1 - scored['copy_share']) * 100)}% independently written"
    return (
        f"{metrics.owners} different owners across {metrics.repos} repos wrote this "
        f"{metrics.occurrences} times ({independent}), about {metrics.loc_total} lines. "
        f"{metrics.fix_commits} fix commits and {metrics.bug_issues} bug issues touch the same code."
    )


async def mine_shapes(context: Context, totals_: tuple[int, int]) -> int:
    cfg = context.workflow.improve.mine
    rows = await context.pool.fetch(
        load_sql("mine_shape_clusters"),
        cfg.min_function_nodes,
        cfg.max_function_loc,
        cfg.min_owners,
        cfg.top_per_kind * 3,
        cfg.soroban_markers,
    )
    count = 0
    for row in rows:
        if row["covered_count"] >= row["occurrences"] * 0.8:
            continue
        members = await member_pairs(context, "members_shape", row["shape_hash"])
        metrics, scored = await evaluate(
            context, members, dict(row), row["owners"], totals_
        )
        sample = {
            "repo": row["sample_repo"],
            "path": row["sample_path"],
            "start": row["sample_start"],
            "end": row["sample_end"],
            "snippet": await snippet(
                context,
                row["sample_repo"],
                row["sample_path"],
                row["sample_start"],
                row["sample_end"],
            ),
        }
        await save(
            context,
            "shape",
            f"Recurring function `{row['common_name']}`: {row['occurrences']} copies, {row['owners']} owners",
            row["shape_hash"],
            metrics,
            scored,
            sample,
            "idiom",
            {"common_name": row["common_name"], "contract_fns": row["contract_fns"]},
            members[0],
        )
        count += 1
        if count >= cfg.top_per_kind:
            break
    return count


async def mine_names(context: Context, totals_: tuple[int, int]) -> int:
    cfg = context.workflow.improve.mine
    rows = await context.pool.fetch(
        load_sql("mine_helper_names"),
        cfg.min_owners,
        cfg.top_per_kind,
        cfg.soroban_markers,
    )
    for row in rows:
        members = await member_pairs(context, "members_name", row["name"])
        metrics, scored = await evaluate(
            context, members, dict(row), row["owners"], totals_
        )
        sample = {
            "repo": row["sample_repo"],
            "path": row["sample_path"],
            "start": row["sample_start"],
            "end": row["sample_end"],
            "snippet": await snippet(
                context,
                row["sample_repo"],
                row["sample_path"],
                row["sample_start"],
                row["sample_end"],
            ),
        }
        await save(
            context,
            "helper",
            f"Hand-written helper `{row['name']}`: {row['owners']} owners rewrote it",
            row["name"],
            metrics,
            scored,
            sample,
            "idiom",
            {"distinct_shapes": row["shapes"]},
            members[0],
        )
    return len(rows)


async def mine_idioms(context: Context, totals_: tuple[int, int]) -> int:
    cfg = context.workflow.improve.mine
    rows = await context.pool.fetch(
        load_sql("mine_idioms"), cfg.min_owners, cfg.top_per_kind, cfg.soroban_markers
    )
    for row in rows:
        members = await member_pairs(context, "members_idiom", row["signature"])
        metrics, scored = await evaluate(
            context, members, dict(row), row["owners"], totals_
        )
        sample = {
            "repo": row["sample_repo"],
            "path": row["sample_path"],
            "start": row["sample_start"],
            "end": row["sample_end"],
            "snippet": await snippet(
                context,
                row["sample_repo"],
                row["sample_path"],
                row["sample_start"],
                row["sample_end"],
            ),
        }
        await save(
            context,
            "idiom",
            f"Contract idiom `{row['common_name']}`: calls {row['signature'][:70]}",
            row["signature"],
            metrics,
            scored,
            sample,
            "idiom",
            None,
            members[0],
        )
    return len(rows)


async def mine_macros(context: Context, totals_: tuple[int, int]) -> int:
    cfg = context.workflow.improve.mine
    rows = await context.pool.fetch(
        load_sql("mine_macros"), cfg.min_macro_owners, cfg.top_per_kind
    )
    for row in rows:
        members = await member_pairs(context, "members_macro", f"def:{row['macro']}")
        base = {"occurrences": row["occurrences"], "bodies": row["occurrences"]}
        metrics, scored = await evaluate(context, members, base, row["owners"], totals_)
        sample = {"repo": row["sample_repo"], "path": row["sample_path"]}
        await save(
            context,
            "macro",
            f"Hand-written macro `{row['macro']}!`: {row['owners']} owners",
            row["macro"],
            metrics,
            scored,
            sample,
            "macro",
            None,
            members[0],
        )
    return len(rows)


async def mine_vocabularies(context: Context, totals_: tuple[int, int]) -> int:
    cfg = context.workflow.improve.mine
    made = 0
    for which, title in (
        ("errors", "Error names every contract invents"),
        ("keys", "Storage key names every contract invents"),
    ):
        rows = await context.pool.fetch(
            load_sql("mine_vocabulary"), which, cfg.min_owners, 25
        )
        if not rows:
            continue
        names = [
            {"name": r["name"], "owners": r["owners"], "repos": r["repos"]}
            for r in rows
        ]
        metrics = Metrics(
            owners=max(r["owners"] for r in rows),
            repos=max(r["repos"] for r in rows),
            occurrences=sum(r["occurrences"] for r in rows),
            bodies=len(rows),
            total_owners=totals_[0],
            total_repos=totals_[1],
        )
        scored = score(metrics, context.workflow.improve.score.weights).model_dump()
        await save(
            context,
            "vocabulary",
            title,
            which,
            metrics,
            scored,
            {"snippet": ", ".join(f"{n['name']} ({n['owners']})" for n in names[:15])},
            "standard-set",
            {"names": names},
        )
        made += 1
    return made


async def mine_terms(context: Context) -> int:
    cfg = context.workflow.improve.mine
    rows = await context.pool.fetch(load_sql("fix_texts"))
    fix_owners: dict[str, set[str]] = {}
    all_owners: dict[str, set[str]] = {}
    fix_owner_total, all_owner_total = set(), set()
    for row in rows:
        words = set(WORD.findall(row["text"].lower())) - STOP
        target = fix_owners if row["is_fix"] else all_owners
        (fix_owner_total if row["is_fix"] else all_owner_total).add(row["owner"])
        for word in words:
            target.setdefault(word, set()).add(row["owner"])
    known = [b.keywords for b in context.catalog.bug_classes]
    counted = Counter()
    for word, owners in fix_owners.items():
        if len(owners) < cfg.min_term_owners:
            continue
        base = len(all_owners.get(word, set())) / max(len(all_owner_total), 1)
        lift = (len(owners) / max(len(fix_owner_total), 1)) / (
            base or 1 / max(len(all_owner_total), 1)
        )
        if lift >= cfg.min_term_lift and not any(re.search(k, word) for k in known):
            counted[word] = lift
    for word, lift in counted.most_common(cfg.top_per_kind):
        owners = len(fix_owners[word])
        await context.pool.execute(
            load_sql("upsert_candidate"),
            f"bug_term:{word}",
            "bug_term",
            f"`{word}` shows up in fixes across {owners} owners, no bug class covers it",
            word,
            owners,
            owners,
            round(lift, 2),
            {"lift": round(lift, 2), "owners": owners},
            f"add `{word}` to a bug class keyword list",
        )
    return len(counted)


async def mine_health(context: Context) -> int:
    rows = await context.pool.fetch(load_sql("pattern_health"))
    flagged = 0
    for row in rows:
        soroban = row["soroban_repos"]
        if soroban < 100:
            continue
        note = None
        if row["occurrences"] == 0:
            note = (
                "dead: it matched nothing in the whole corpus, drop or fix the matcher"
            )
        elif row["repos"] > 0.9 * soroban and row["category"] != "test":
            note = (
                "noisy: it matches almost every repo, it carries no signal, tighten it"
            )
        if note:
            flagged += 1
            await context.pool.execute(
                load_sql("upsert_candidate"),
                f"health:{row['id']}",
                "health",
                f"Pattern `{row['id']}` is {note.split(':')[0]}",
                row["id"],
                row["repos"],
                row["occurrences"],
                50,
                dict(row),
                note,
            )
    return flagged


async def promote_patterns(context: Context) -> int:
    accept = context.workflow.improve.accept
    if accept.patterns != "auto":
        return 0
    rows = await context.pool.fetch(
        "SELECT signature, repos, evidence FROM catalog_candidates "
        "WHERE kind = 'helper' AND repos >= $1 ORDER BY score DESC LIMIT $2",
        accept.min_owners,
        accept.max_mined_patterns,
    )
    keep = [f"mined.fn.{row['signature']}" for row in rows]
    await context.pool.execute(
        "UPDATE patterns SET status = 'retired' "
        "WHERE origin = 'mined' AND status = 'active' AND id <> ALL($1::text[])",
        keep,
    )
    await context.pool.execute(
        "UPDATE patterns SET status = 'active' "
        "WHERE origin = 'mined' AND status = 'retired' AND id = ANY($1::text[])",
        keep,
    )
    for row in rows:
        name = row["signature"]
        matcher = {
            "kind": "function",
            "name": f"^{re.escape(name)}$",
            "skip_tests": True,
        }
        await context.pool.execute(
            load_sql("upsert_mined_pattern"),
            f"mined.fn.{name}",
            f"Function `{name}` hand-written in {row['repos']} repos (found by the miner)",
            json.dumps(matcher),
        )
    return len(rows)


MIN_EVALUATED = 20


async def mine_queries(context: Context) -> int:
    cfg = context.workflow.improve.mine
    rows = await context.pool.fetch(load_sql("mine_topics"), cfg.min_topic_repos)
    queries = " ".join(
        context.workflow.discover.repository_queries
        + context.workflow.discover.code_queries
    )
    floor = context.workflow.improve.accept.min_topic_precision
    generic = [
        r["topic"]
        for r in rows
        if r["evaluated"] >= MIN_EVALUATED and r["precision"] < floor
    ]
    if generic:
        await context.pool.execute(load_sql("reject_query_candidates"), generic)
    fresh = [
        r
        for r in rows
        if r["precision"] is not None
        and r["precision"] >= floor
        and f"topic:{r['topic']}" not in queries
    ]
    for row in fresh:
        await context.pool.execute(
            load_sql("upsert_candidate"),
            f"query:topic:{row['topic']}",
            "query",
            f"Search `topic:{row['topic']}`: {row['repos']} of {row['carriers']} repos carrying it are soroban",
            row["topic"],
            row["repos"],
            row["repos"],
            row["repos"],
            {"topic": row["topic"]},
            f'- "topic:{row["topic"]}"',
        )
    if context.workflow.improve.accept.queries == "auto":
        await context.pool.execute(
            load_sql("accept_query_candidate"),
            context.workflow.improve.accept.min_topic_repos,
        )
    return len(fresh)


@stage("catalog.mine")
async def mine(context: Context, _: Stage) -> None:
    started = await context.pool.fetchval("SELECT now()")
    totals_ = await totals(context)
    detail = {
        "shapes": await mine_shapes(context, totals_),
        "helpers": await mine_names(context, totals_),
        "idioms": await mine_idioms(context, totals_),
        "macros": await mine_macros(context, totals_),
        "vocabularies": await mine_vocabularies(context, totals_),
        "bug_terms": await mine_terms(context),
        "health": await mine_health(context),
        "queries": await mine_queries(context),
        "promoted_patterns": await promote_patterns(context),
    }
    pruned = await context.pool.fetchval(
        "WITH gone AS (DELETE FROM proposals WHERE origin = 'mined' "
        "AND scored_at < $1 RETURNING 1) SELECT count(*) FROM gone",
        started,
    )
    await context.pool.execute(
        "DELETE FROM catalog_candidates WHERE kind IN "
        "('shape', 'helper', 'idiom', 'macro', 'vocabulary', 'health') "
        "AND last_seen_at < $1",
        started,
    )
    detail["pruned_stale_proposals"] = pruned
    context.detail.update(detail)
    context.items = sum(detail.values())
    log.info("mined %s", detail)
