from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Network = Literal["mainnet", "testnet", "both"]
NodeKind = Literal["proposal", "repo", "contract", "library", "bug_class"]


class Wrapped(BaseModel):
    soroban_repos: int
    stellar_repos: int
    mainnet_repos: int
    testnet_repos: int
    proposals: int
    needs: int
    patterns: int
    mainnet_contracts: int
    testnet_contracts: int
    live_contracts: int
    functions: int
    commits: int
    issues: int
    comments: int
    first_day: date | None
    last_day: date | None
    top_proposals: list["ProposalItem"]
    top_patterns: list["PatternItem"]
    top_needs: list["NeedItem"]
    days: list["ChainDay"]
    top_contracts: list["TopContract"]
    top_edges: list["TopEdge"]
    patterns_warming: bool = False
    chain_warming: bool = False


class GraphNode(BaseModel):
    id: str
    kind: NodeKind
    label: str
    network: Network | None = None
    score: float = 0
    weight: float = Field(default=0, description="score normalised within its kind")
    degree: int = 0
    stars: int | None = None
    live: bool | None = None
    status: str | None = None
    origin: str | None = None
    link: str | None = None
    language: str | None = None
    pushed_at: datetime | None = None


class GraphEdge(BaseModel):
    src: str
    dst: str
    kind: str
    weight: float = 1


class GraphResponse(BaseModel):
    scope: Literal["ecosystem", "chain"]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int
    truncated: bool
    warming: bool = False


class NeighbourResponse(BaseModel):
    id: str
    center: GraphNode | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ProposalItem(BaseModel):
    id: str
    name: str
    kind: str
    summary: str
    origin: str
    status: str
    score: float
    covered_by: list[str]
    components: dict[str, float] = {}
    weighted: dict[str, float] = {}
    repos: int
    owners: int
    mainnet_repos: int
    fix_commits: int
    occurrences: int
    copy_share: float
    comments: int


class FixExample(BaseModel):
    sha: str
    date: str
    repo: str
    message: str


class CodeSample(BaseModel):
    repo: str | None = None
    path: str | None = None
    start: int | None = None
    end: int | None = None
    snippet: str | None = None


class RepoRef(BaseModel):
    full_name: str
    weight: int = 0
    stars: int
    language: str | None
    description: str | None = None
    networks: list[str]
    pushed_at: datetime | None


class PatternRef(BaseModel):
    id: str
    role: str
    category: str
    description: str


class BugClass(BaseModel):
    id: str
    name: str
    description: str
    severity: str


class ContractRef(BaseModel):
    network: str
    contract_id: str
    live: bool
    link: str
    repo: str | None = None


class ProposalDetail(ProposalItem):
    sketch: str | None
    scored_at: datetime | None
    metrics: dict[str, float] = {}
    roles: dict[str, dict[str, int]] = {}
    thresholds: dict[str, float] = {}
    share_of_repos: float = 0
    sample: CodeSample | None = None
    fix_examples: list[FixExample] = []
    linked_repos: list[RepoRef]
    linked_repo_total: int
    patterns: list[PatternRef]
    bug_classes: list[BugClass]


class NeedItem(BaseModel):
    id: str
    title: str
    category: str
    origin: str
    status: str
    score: float
    summary: str
    pain_issues: int
    pain_owners: int
    issues: int
    repos: int
    owners: int
    open_issues: int
    custom_repos: int
    questions: int
    components: dict[str, float] = {}
    priority: str | None
    comments: int
    tools: list[str] = []


class Evidence(BaseModel):
    kind: str
    repo: str | None
    ref: str
    relevance: float
    title: str | None
    snippet: str | None
    url: str | None
    created_at: datetime | None


class EvidenceCount(BaseModel):
    kind: str
    total: int


class ToolRef(BaseModel):
    id: str
    name: str
    category: str
    url: str | None
    description: str
    relation: str
    relevance: float


class Affected(BaseModel):
    stack: str
    repos: int


class ExistingTool(BaseModel):
    id: str
    name: str
    url: str | None = None
    relation: str


class Highlight(BaseModel):
    kind: str
    repo: str | None = None
    title: str | None = None
    snippet: str | None = None
    url: str | None = None
    relevance: float = 0


class GapEvidence(BaseModel):
    title: str
    url: str
    reactions: int = 0
    comments: int = 0


class GapItem(BaseModel):
    item: str
    status: str
    coverage: float = 0
    evidence: list[GapEvidence] = []


class GapTool(BaseModel):
    tool: str
    name: str
    url: str | None = None
    verdict: str
    summary: str
    reasons: list[str] = []
    items: list[GapItem] = []


class Rfp(BaseModel):
    title: str = ""
    problem: str = ""
    gap: str = ""
    priority: str = ""
    deliverables: list[str] = []
    success_metrics: list[str] = []
    who_is_affected: list[Affected] = []
    existing_tools: list[ExistingTool] = []
    gap_analysis: list[GapTool] = []
    evidence_highlights: list[Highlight] = []


class NeedDetail(BaseModel):
    id: str
    title: str
    category: str
    origin: str
    status: str
    score: float
    summary: str
    demand: dict[str, float]
    components: dict[str, float] = {}
    evidence_rows: dict[str, int] = {}
    rfp: Rfp
    scored_at: datetime | None
    comments: int
    evidence: list[Evidence]
    evidence_counts: list[EvidenceCount]
    tools: list[ToolRef]


class PatternItem(BaseModel):
    id: str
    category: str
    description: str
    origin: str
    status: str
    diff: str | None
    repos: int
    occurrences: int
    sample: str | None
    sample_repo: str | None
    sample_path: str | None
    proposals: list[str] = []


class RepoItem(BaseModel):
    full_name: str
    stars: int
    language: str | None
    description: str | None
    networks: list[str]
    pushed_at: datetime | None
    rust_loc: int
    window_commits: int | None
    is_soroban: bool
    is_stellar: bool
    topics: list[str]
    proposals: int


class RepoList(BaseModel):
    total: int
    items: list[RepoItem]


class RepoProposal(BaseModel):
    id: str
    name: str
    score: float
    status: str
    origin: str
    weight: int


class RepoPattern(BaseModel):
    id: str
    category: str
    occurrences: int
    sample_path: str | None
    sample: str | None


class RepoNeed(BaseModel):
    id: str
    title: str
    evidence: int
    relevance: float


class RepoDetail(BaseModel):
    full_name: str
    url: str
    owner: str
    description: str | None
    homepage: str | None
    topics: list[str]
    language: str | None
    license: str | None
    stars: int
    forks: int
    open_issues: int
    size_kb: int
    archived: bool
    is_fork: bool
    created_at: datetime | None
    pushed_at: datetime | None
    networks: list[str]
    window_commits: int | None
    total_commits: int | None
    is_soroban: bool
    is_stellar: bool
    rust_files: int
    rust_loc: int
    contract_crates: int
    stack: list[str]
    stellar_libs: list[str]
    languages: dict[str, int]
    comments: int
    proposals: list[RepoProposal]
    patterns: list[RepoPattern]
    contracts: list[ContractRef]
    needs: list[RepoNeed]


class ChainDay(BaseModel):
    network: str
    day: date
    ledgers: int
    transactions: int
    failed_transactions: int
    operations: int
    contract_calls: int
    contracts_called: int


class ChainActivity(BaseModel):
    days: list[ChainDay]
    first_day: date | None
    last_day: date | None


class TopContract(BaseModel):
    network: str
    contract_id: str
    invocations: int
    successful: int
    peak_daily_callers: int
    active_days: int
    first_day: date
    last_day: date
    live: bool | None
    repos: list[str] = []


class TopEdge(BaseModel):
    network: str
    caller: str
    callee: str
    calls: int
    successful: int
    active_days: int


class ChainTop(BaseModel):
    contracts: list[TopContract]
    edges: list[TopEdge]
    warming: bool = False


class ContractDay(BaseModel):
    day: date
    invocations: int
    successful: int
    callers: int


class ContractDetail(BaseModel):
    network: str
    contract_id: str
    executable: str
    wasm_hash: str | None
    live: bool
    live_until_ledger: int | None
    wasm_size: int | None
    sdk_version: str | None
    source_repo: str | None
    function_names: list[str]
    invocations: int
    days: list[ContractDay]
    repos: list[RepoRef]


class SearchHit(BaseModel):
    kind: Literal["proposal", "need", "pattern", "repo", "tool", "contract"]
    id: str
    label: str
    sub: str
    score: float = 0


class SearchResponse(BaseModel):
    q: str
    hits: list[SearchHit]


class PatternList(BaseModel):
    items: list[PatternItem]
    warming: bool = False


Wrapped.model_rebuild()


class Comment(BaseModel):
    id: int
    author: str
    body: str
    created_at: datetime


class CommentCreate(BaseModel):
    target_kind: Literal[
        "repo", "proposal", "pattern", "contract", "node", "need", "tool"
    ]
    target_id: str = Field(min_length=1, max_length=300)
    author: str = Field(default="anonymous", max_length=80)
    body: str = Field(min_length=1, max_length=4000)
