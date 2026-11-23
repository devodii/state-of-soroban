import logging
from collections import defaultdict

from state_of_soroban.runner import Context, stage
from state_of_soroban.sql_loader import load_sql
from state_of_soroban.stages.mine import evaluate, member_pairs, totals
from state_of_soroban.workflow import Stage

log = logging.getLogger("state_of_soroban")

ROLES = ("boilerplate", "footgun", "adopted")


async def score_seeds(context: Context, totals_: tuple[int, int]) -> int:
    links: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in await context.pool.fetch(load_sql("seed_patterns")):
        links[row["proposal"]][row["role"]].append(row["pattern"])
    await context.pool.execute(load_sql("refresh_seed_proposal_repos"))
    seeds = await context.pool.fetch(load_sql("seed_proposals"))
    for seed in seeds:
        roles = links[seed["id"]]
        used = roles["boilerplate"] + roles["footgun"]
        base = dict(await context.pool.fetchrow(load_sql("seed_metrics"), used))
        members = await member_pairs(context, "members_patterns", used)
        metrics, scored = await evaluate(
            context, members, base, base["owners"], totals_
        )
        breakdown = {}
        for role in ROLES:
            row = await context.pool.fetchrow(load_sql("seed_metrics"), roles[role])
            breakdown[role] = {
                "repos": row["repos"],
                "owners": row["owners"],
                "occurrences": row["occurrences"],
            }
        share = base["repos"] / totals_[1]
        if totals_[1] < 100:
            status = "insufficient data"
        elif (
            base["repos"] >= seed["min_repos"]
            and share >= float(seed["min_share"])
            and base["occurrences"] >= seed["min_occurrences"]
        ):
            status = "supported"
        else:
            status = "unsupported"
        evidence = {
            "metrics": metrics.model_dump(),
            "components": scored["components"],
            "weighted": scored["weighted"],
            "copy_share": scored["copy_share"],
            "fix_examples": scored.get("fix_examples", []),
            "roles": breakdown,
            "share_of_repos": round(share, 4),
            "thresholds": {
                "min_repos": seed["min_repos"],
                "min_share": float(seed["min_share"]),
                "min_occurrences": seed["min_occurrences"],
            },
        }
        await context.pool.execute(
            load_sql("update_proposal_score"),
            seed["id"],
            scored["score"],
            evidence,
            status,
        )
    return len(seeds)


async def lifecycle_mined(context: Context) -> int:
    accept = context.workflow.improve.accept
    rows = await context.pool.fetch(load_sql("mined_proposals"))
    for row in rows:
        score_value = float(row["evidence"].get("score", 0))
        owners = row["evidence"]["metrics"]["owners"]
        stored = await context.pool.fetchval(
            "SELECT score FROM proposals WHERE id = $1", row["id"]
        )
        score_value = float(stored)
        strong = score_value >= accept.min_score and owners >= accept.min_owners
        status = (
            ("accepted" if accept.policy == "auto" else "strong")
            if strong
            else "proposed"
        )
        await context.pool.execute(
            "UPDATE proposals SET status = $2 WHERE id = $1", row["id"], status
        )
    return len(rows)


@stage("catalog.score")
async def score_all(context: Context, _: Stage) -> None:
    totals_ = await totals(context)
    seeds = await score_seeds(context, totals_)
    mined = await lifecycle_mined(context)
    context.items = seeds + mined
    context.detail.update({"seeds": seeds, "mined": mined})
    log.info("scored %s seeds and %s mined proposals", seeds, mined)
