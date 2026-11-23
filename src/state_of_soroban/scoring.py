import math

from pydantic import BaseModel, Field

from state_of_soroban.workflow import Weights

FIX_SATURATION = 25
LOC_SATURATION = 20000


class Metrics(BaseModel):
    owners: int = 0
    repos: int = 0
    occurrences: int = 0
    bodies: int = 0
    loc_total: int = 0
    mainnet_repos: int = 0
    recent_repos: int = 0
    fix_commits: int = 0
    bug_issues: int = 0
    adopted_repos: int = 0
    total_owners: int = 1
    total_repos: int = 1


class Scored(BaseModel):
    score: float
    components: dict[str, float] = Field(default_factory=dict)
    weighted: dict[str, float] = Field(default_factory=dict)
    copy_share: float = 0.0


def ratio(part: int, whole: int) -> float:
    return min(1.0, part / whole) if whole else 0.0


def score(metrics: Metrics, weights: Weights) -> Scored:
    independence = ratio(metrics.bodies, metrics.occurrences)
    components = {
        "owners": math.log1p(metrics.owners) / math.log1p(max(metrics.total_owners, 2)),
        "independence": independence,
        "mainnet": ratio(metrics.mainnet_repos, metrics.repos),
        "recency": ratio(metrics.recent_repos, metrics.repos),
        "fixes": min(
            1.0,
            math.log1p(metrics.fix_commits + metrics.bug_issues)
            / math.log1p(FIX_SATURATION),
        ),
        "loc": min(1.0, math.log1p(metrics.loc_total) / math.log1p(LOC_SATURATION)),
        "covered": ratio(metrics.adopted_repos, metrics.repos),
    }
    weight = weights.model_dump()
    weighted = {name: weight[name] * value for name, value in components.items()}
    positive = sum(w for w in weight.values() if w > 0) or 1.0
    total = max(0.0, 100 * sum(weighted.values()) / positive)
    return Scored(
        score=round(min(total, 100.0), 2),
        components={k: round(v, 4) for k, v in components.items()},
        weighted={k: round(v, 4) for k, v in weighted.items()},
        copy_share=round(1 - independence, 4) if metrics.occurrences else 0.0,
    )
