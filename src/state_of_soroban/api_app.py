import asyncio
import math
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from state_of_soroban.api_models import (
    BugClass,
    ChainActivity,
    ChainDay,
    ChainTop,
    CodeSample,
    Comment,
    CommentCreate,
    ContractDay,
    ContractDetail,
    ContractRef,
    Evidence,
    EvidenceCount,
    FixExample,
    GraphEdge,
    GraphNode,
    GraphResponse,
    NeedDetail,
    NeedItem,
    NeighbourResponse,
    PatternItem,
    PatternList,
    PatternRef,
    ProposalDetail,
    ProposalItem,
    RepoDetail,
    RepoItem,
    RepoList,
    RepoNeed,
    RepoPattern,
    RepoProposal,
    RepoRef,
    Rfp,
    SearchHit,
    SearchResponse,
    ToolRef,
    TopContract,
    TopEdge,
    Wrapped,
)
from state_of_soroban.sql_loader import load_sql

SHORT_TTL = 600.0
GRAPH_TTL = 3600.0
LONG_TTL = 14400.0
FIXED_KINDS = {"proposal", "library", "bug_class"}
CHAIN_NODES = 240
WARM_PATIENCE = 2.5

router = APIRouter(prefix="/api/v2", tags=["v2"])


class Cache:
    def __init__(self) -> None:
        self.values: dict[str, tuple[float, Any]] = {}
        self.busy: dict[str, asyncio.Task[Any]] = {}

    async def fill(self, key: str, make: Callable[[], Awaitable[Any]]) -> Any:
        try:
            value = await make()
            self.values[key] = (time.monotonic(), value)
            return value
        finally:
            self.busy.pop(key, None)

    def start(self, key: str, make: Callable[[], Awaitable[Any]]) -> asyncio.Task[Any]:
        task = self.busy.get(key)
        if task is None:
            task = asyncio.create_task(self.fill(key, make))
            self.busy[key] = task
        return task

    def peek(
        self, key: str, make: Callable[[], Awaitable[Any]], ttl: float
    ) -> Any | None:
        cached = self.values.get(key)
        if cached is None:
            self.start(key, make)
            return None
        if time.monotonic() - cached[0] > ttl:
            self.start(key, make)
        return cached[1]

    async def get(
        self,
        key: str,
        make: Callable[[], Awaitable[Any]],
        ttl: float = SHORT_TTL,
        patience: float | None = None,
    ) -> Any | None:
        cached = self.values.get(key)
        if cached is not None:
            if time.monotonic() - cached[0] > ttl:
                self.start(key, make)
            return cached[1]
        task = self.start(key, make)
        if patience is None:
            return await asyncio.shield(task)
        done, _ = await asyncio.wait({task}, timeout=patience)
        return task.result() if done else None


def cache_of(request: Request) -> Cache:
    return request.app.state.v2


def pool_of(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


async def rows(pool: asyncpg.Pool, name: str, *args: Any) -> list[dict[str, Any]]:
    async with pool.acquire() as connection:
        found = await connection.fetch(load_sql(name), *args)
    return [dict(row) for row in found]


def network_of(
    networks: list[str] | None,
) -> Literal["mainnet", "testnet", "both"] | None:
    values = set(networks or [])
    main, test = "mainnet" in values, "testnet" in values
    if main and test:
        return "both"
    if main:
        return "mainnet"
    if test:
        return "testnet"
    return None


class FullGraph(BaseModel):
    nodes: dict[str, GraphNode]
    edges: list[GraphEdge]
    adjacency: dict[str, list[int]]


def normalise(nodes: dict[str, GraphNode]) -> None:
    peak: dict[str, float] = defaultdict(float)
    for node in nodes.values():
        peak[node.kind] = max(peak[node.kind], node.score)
    for node in nodes.values():
        top = peak[node.kind]
        node.weight = round(node.score / top, 4) if top > 0 else 0


def build_graph(
    node_rows: list[dict[str, Any]], edge_rows: list[dict[str, Any]]
) -> FullGraph:
    nodes: dict[str, GraphNode] = {}
    for row in node_rows:
        props = row["props"] or {}
        kind = row["kind"]
        network = None
        if kind == "repo":
            network = network_of(row["networks"])
        elif kind == "contract":
            network = props.get("network")
        score = 0.0
        if kind == "proposal":
            score = float(row["proposal_score"] or props.get("score") or 0)
        nodes[row["id"]] = GraphNode(
            id=row["id"],
            kind=kind,
            label=row["label"],
            network=network,
            score=score,
            stars=row["stars"],
            live=row["live"] if kind == "contract" else None,
            status=row["status"] or props.get("status"),
            origin=row["origin"] or props.get("origin"),
            link=props.get("link"),
            language=row["language"],
            pushed_at=row["pushed_at"],
        )
    edges: list[GraphEdge] = []
    adjacency: dict[str, list[int]] = defaultdict(list)
    for row in edge_rows:
        if row["src"] not in nodes or row["dst"] not in nodes:
            continue
        adjacency[row["src"]].append(len(edges))
        adjacency[row["dst"]].append(len(edges))
        edges.append(
            GraphEdge(
                src=row["src"],
                dst=row["dst"],
                kind=row["kind"],
                weight=float(row["weight"]),
            )
        )
    for node_id, node in nodes.items():
        node.degree = len(adjacency[node_id])
    for edge in edges:
        if edge.kind == "hand_rolls":
            nodes[edge.src].score += nodes[edge.dst].score * edge.weight / 10
    for node in nodes.values():
        if node.kind == "contract":
            node.score = math.log1p(node.degree)
        if node.kind in ("library", "bug_class"):
            node.score = 1 + node.degree
    normalise(nodes)
    return FullGraph(nodes=nodes, edges=edges, adjacency=dict(adjacency))


async def load_graph(pool: asyncpg.Pool) -> FullGraph:
    nodes, edges = await asyncio.gather(
        rows(pool, "v2_graph_nodes"), rows(pool, "v2_graph_edges")
    )
    return build_graph(nodes, edges)


def other_end(edge: GraphEdge, node_id: str) -> str:
    return edge.dst if edge.src == node_id else edge.src


def select_ecosystem(
    graph: FullGraph, limit: int, network: str | None, focus: str | None
) -> GraphResponse:
    pool = {
        node_id: node
        for node_id, node in graph.nodes.items()
        if network is None
        or node.kind in FIXED_KINDS
        or node.network in (network, "both")
    }
    chosen = {i: n for i, n in pool.items() if n.kind in FIXED_KINDS}
    if focus and focus in pool:
        chosen[focus] = pool[focus]
        around = sorted(
            graph.adjacency.get(focus, []), key=lambda i: -graph.edges[i].weight
        )
        for index in around[:120]:
            other = other_end(graph.edges[index], focus)
            if other in pool:
                chosen[other] = pool[other]
    repos = sorted(
        (n for n in pool.values() if n.kind == "repo" and n.id not in chosen),
        key=lambda n: (-n.score, -(n.stars or 0)),
    )
    for node in repos[: int(max(limit - len(chosen), 0) * 0.55)]:
        chosen[node.id] = node
    contracts = [
        n for n in pool.values() if n.kind == "contract" and n.id not in chosen
    ]
    anchored = {
        n.id: any(
            other_end(graph.edges[i], n.id) in chosen
            for i in graph.adjacency.get(n.id, [])
        )
        for n in contracts
    }
    contracts.sort(key=lambda n: (not anchored[n.id], -n.degree))
    for node in contracts[: max(limit - len(chosen), 0)]:
        if anchored[node.id]:
            chosen[node.id] = node
    return GraphResponse(
        scope="ecosystem",
        nodes=list(chosen.values()),
        edges=[e for e in graph.edges if e.src in chosen and e.dst in chosen],
        total_nodes=len(pool),
        total_edges=len(graph.edges),
        truncated=len(chosen) < len(pool),
    )


class ChainSnapshot(BaseModel):
    contracts: list[TopContract]
    edges: list[TopEdge]


async def load_chain_top(pool: asyncpg.Pool) -> ChainSnapshot:
    contract_rows = await rows(pool, "v2_chain_top_contracts", 300)
    edge_rows = await rows(pool, "v2_chain_top_edges", 200)
    return ChainSnapshot(
        contracts=[
            TopContract.model_validate({**r, "repos": r["repos"] or []})
            for r in contract_rows
        ],
        edges=[TopEdge.model_validate(r) for r in edge_rows],
    )


class ChainGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


def chain_id(network: str, contract_id: str) -> str:
    return f"contract:{network}:{contract_id}"


async def load_chain_graph(pool: asyncpg.Pool, top: ChainSnapshot) -> ChainGraph:
    picked = top.contracts[:CHAIN_NODES]
    ids = [c.contract_id for c in picked]
    found = await rows(
        pool, "v2_chain_edges_among", [c.network for c in picked], ids, ids
    )
    members = {(c.network, c.contract_id) for c in picked}
    edges = [
        GraphEdge(
            src=chain_id(r["network"], r["caller"]),
            dst=chain_id(r["network"], r["callee"]),
            kind="calls",
            weight=math.log1p(float(r["calls"])),
        )
        for r in found
        if (r["network"], r["callee"]) in members and r["caller"] != r["callee"]
    ]
    degree: dict[str, int] = defaultdict(int)
    for edge in edges:
        degree[edge.src] += 1
        degree[edge.dst] += 1
    peak = math.log1p(max((c.invocations for c in picked), default=1))
    nodes = [
        GraphNode(
            id=chain_id(c.network, c.contract_id),
            kind="contract",
            label=c.contract_id[:8],
            network="mainnet" if c.network == "mainnet" else "testnet",
            score=float(c.invocations),
            weight=round(math.log1p(c.invocations) / peak, 4),
            degree=degree[chain_id(c.network, c.contract_id)],
            live=c.live,
            link="repo" if c.repos else None,
        )
        for c in picked
    ]
    return ChainGraph(nodes=nodes, edges=edges)


async def proposal_items(pool: asyncpg.Pool, cache: Cache) -> list[ProposalItem]:
    async def make() -> list[ProposalItem]:
        found = await rows(pool, "v2_proposals", 500)
        return [
            ProposalItem.model_validate(
                {
                    **r,
                    "components": r["components"] or {},
                    "weighted": r["weighted"] or {},
                }
            )
            for r in found
        ]

    return await cache.get("proposals", make, SHORT_TTL)


async def need_items(pool: asyncpg.Pool, cache: Cache) -> list[NeedItem]:
    async def make() -> list[NeedItem]:
        found = await rows(pool, "v2_needs", 500)
        return [
            NeedItem.model_validate(
                {**r, "components": r["components"] or {}, "tools": r["tools"] or []}
            )
            for r in found
        ]

    return await cache.get("needs", make, SHORT_TTL)


async def load_patterns(pool: asyncpg.Pool) -> list[PatternItem]:
    found = await rows(pool, "v2_patterns")
    return [
        PatternItem.model_validate({**r, "proposals": r["proposals"] or []})
        for r in found
    ]


async def build_wrapped(pool: asyncpg.Pool, cache: Cache) -> Wrapped:
    counts, days, top_proposals, top_needs = await asyncio.gather(
        rows(pool, "v2_summary_counts"),
        rows(pool, "v2_chain_days"),
        proposal_items(pool, cache),
        need_items(pool, cache),
    )
    return Wrapped(
        **counts[0],
        top_proposals=top_proposals[:14],
        top_patterns=[],
        top_needs=top_needs[:12],
        days=[ChainDay.model_validate(d) for d in days],
        top_contracts=[],
        top_edges=[],
    )


@router.get("/wrapped", response_model=Wrapped)
async def wrapped(request: Request) -> Wrapped:
    pool, cache = pool_of(request), cache_of(request)
    base = await cache.get("wrapped", lambda: build_wrapped(pool, cache), SHORT_TTL)
    patterns_ = cache.peek("patterns", lambda: load_patterns(pool), LONG_TTL)
    top = cache.peek("chain_top", lambda: load_chain_top(pool), LONG_TTL)
    return base.model_copy(
        update={
            "top_patterns": [p for p in (patterns_ or []) if p.repos > 0][:10],
            "top_contracts": top.contracts[:10] if top else [],
            "top_edges": top.edges[:10] if top else [],
            "patterns_warming": patterns_ is None,
            "chain_warming": top is None,
        }
    )


@router.get("/graph", response_model=GraphResponse)
async def graph(
    request: Request,
    scope: Literal["ecosystem", "chain"] = "ecosystem",
    focus: str | None = None,
    limit: int = Query(default=900, ge=50, le=4000),
    network: Literal["mainnet", "testnet"] | None = None,
) -> GraphResponse:
    pool, cache = pool_of(request), cache_of(request)
    if scope == "ecosystem":
        full = await cache.get("graph", lambda: load_graph(pool), GRAPH_TTL)
        return select_ecosystem(full, limit, network, focus)
    top = await cache.get(
        "chain_top", lambda: load_chain_top(pool), LONG_TTL, WARM_PATIENCE
    )
    if top is None:
        return GraphResponse(
            scope="chain",
            nodes=[],
            edges=[],
            total_nodes=0,
            total_edges=0,
            truncated=False,
            warming=True,
        )
    chain = await cache.get(
        "chain_graph", lambda: load_chain_graph(pool, top), LONG_TTL, WARM_PATIENCE
    )
    if chain is None:
        return GraphResponse(
            scope="chain",
            nodes=[],
            edges=[],
            total_nodes=0,
            total_edges=0,
            truncated=False,
            warming=True,
        )
    nodes = [n for n in chain.nodes if network is None or n.network == network][:limit]
    kept = {n.id for n in nodes}
    return GraphResponse(
        scope="chain",
        nodes=nodes,
        edges=[e for e in chain.edges if e.src in kept and e.dst in kept],
        total_nodes=len(chain.nodes),
        total_edges=len(chain.edges),
        truncated=len(nodes) < len(chain.nodes),
    )


def repo_node(row: dict[str, Any], score: float) -> GraphNode:
    return GraphNode(
        id=f"repo:{row['full_name']}",
        kind="repo",
        label=row["full_name"],
        network=network_of(row["networks"]),
        score=score,
        weight=min(1.0, math.log1p(row["stars"] or 0) / 8),
        stars=row["stars"],
        language=row["language"],
        pushed_at=row["pushed_at"],
    )


def contract_node(
    network: str, contract_id: str, live: bool | None, link: str | None
) -> GraphNode:
    return GraphNode(
        id=chain_id(network, contract_id),
        kind="contract",
        label=contract_id[:8],
        network="mainnet" if network == "mainnet" else "testnet",
        weight=0.3,
        live=live,
        link=link,
    )


@router.get("/neighbours", response_model=NeighbourResponse)
async def neighbours(
    request: Request, id: str, limit: int = Query(default=40, ge=1, le=150)
) -> NeighbourResponse:
    pool, cache = pool_of(request), cache_of(request)
    full = await cache.get("graph", lambda: load_graph(pool), GRAPH_TTL)
    nodes: dict[str, GraphNode] = {}
    edges: dict[tuple[str, str, str], GraphEdge] = {}

    def link(src: str, dst: str, kind: str, weight: float) -> None:
        edges[(src, dst, kind)] = GraphEdge(src=src, dst=dst, kind=kind, weight=weight)

    known = sorted(full.adjacency.get(id, []), key=lambda i: -full.edges[i].weight)
    for index in known[:limit]:
        edge = full.edges[index]
        nodes[other_end(edge, id)] = full.nodes[other_end(edge, id)]
        link(edge.src, edge.dst, edge.kind, edge.weight)
    kind, _, rest = id.partition(":")
    if kind == "proposal":
        for row in await rows(pool, "v2_neighbour_proposal_repos", rest, limit):
            node = repo_node(row, float(row["weight"]))
            nodes.setdefault(node.id, node)
            link(node.id, id, "hand_rolls", float(row["weight"]))
    elif kind == "repo":
        found_proposals, found_contracts = await asyncio.gather(
            rows(pool, "v2_neighbour_repo_proposals", rest, limit),
            rows(pool, "v2_neighbour_repo_contracts", rest, limit),
        )
        for row in found_proposals:
            node = GraphNode(
                id=f"proposal:{row['id']}",
                kind="proposal",
                label=row["name"][:80],
                score=float(row["score"]),
                weight=min(1.0, float(row["score"]) / 50),
                status=row["status"],
                origin=row["origin"],
            )
            nodes.setdefault(node.id, node)
            link(id, node.id, "hand_rolls", float(row["weight"]))
        for row in found_contracts:
            node = contract_node(
                row["network"], row["contract_id"], row["live"], row["link"]
            )
            nodes.setdefault(node.id, node)
            link(id, node.id, "deploys", 3)
    elif kind == "contract":
        network, _, contract_id = rest.partition(":")
        calls, linked = await asyncio.gather(
            rows(pool, "v2_neighbour_contract_calls", network, contract_id, limit),
            rows(pool, "v2_neighbour_contract_repos", network, contract_id, limit),
        )
        for row in calls:
            node = contract_node(network, row["other"], None, None)
            nodes.setdefault(node.id, node)
            weight = math.log1p(float(row["calls"]))
            if row["direction"] == "out":
                link(id, node.id, "calls", weight)
            else:
                link(node.id, id, "calls", weight)
        for row in linked:
            node = repo_node(row, 0)
            nodes.setdefault(node.id, node)
            link(node.id, id, "deploys", 3)
    nodes.pop(id, None)
    center = full.nodes.get(id)
    if center is None and kind == "repo":
        index = await cache.get(
            "repo_index", lambda: load_repo_index(pool), LONG_TTL / 3
        )
        found = next((r for r in index if r.full_name == rest), None)
        if found:
            center = repo_node(found.model_dump(), 0)
    if center is None and kind == "contract":
        network, _, contract_id = rest.partition(":")
        center = contract_node(network, contract_id, None, None)
    return NeighbourResponse(
        id=id, center=center, nodes=list(nodes.values()), edges=list(edges.values())
    )


@router.get("/proposals", response_model=list[ProposalItem])
async def proposals(request: Request) -> list[ProposalItem]:
    return await proposal_items(pool_of(request), cache_of(request))


@router.get("/proposals/{proposal_id}", response_model=ProposalDetail)
async def proposal(request: Request, proposal_id: str) -> ProposalDetail:
    pool, cache = pool_of(request), cache_of(request)

    async def make() -> ProposalDetail | None:
        head = await rows(pool, "v2_proposal", proposal_id)
        listing = next(
            (p for p in await proposal_items(pool, cache) if p.id == proposal_id),
            None,
        )
        if not head or listing is None:
            return None
        linked, found_patterns, bugs = await asyncio.gather(
            rows(pool, "v2_proposal_repos", proposal_id, 60),
            rows(pool, "v2_proposal_patterns", proposal_id),
            rows(pool, "v2_proposal_bugs", proposal_id),
        )
        evidence = head[0]["evidence"] or {}
        sample = evidence.get("sample")
        return ProposalDetail(
            **listing.model_dump(),
            sketch=head[0]["sketch"],
            scored_at=head[0]["scored_at"],
            metrics=evidence.get("metrics", {}),
            roles=evidence.get("roles", {}),
            thresholds=evidence.get("thresholds", {}),
            share_of_repos=evidence.get("share_of_repos", 0),
            sample=CodeSample.model_validate(sample) if sample else None,
            fix_examples=[
                FixExample.model_validate(f) for f in evidence.get("fix_examples", [])
            ],
            linked_repos=[RepoRef.model_validate(r) for r in linked],
            linked_repo_total=linked[0]["total"] if linked else 0,
            patterns=[PatternRef.model_validate(r) for r in found_patterns],
            bug_classes=[BugClass.model_validate(r) for r in bugs],
        )

    found = await cache.get(f"proposal:{proposal_id}", make, SHORT_TTL)
    if found is None:
        raise HTTPException(404, "unknown proposal")
    return found


@router.get("/proposals/{proposal_id}/contracts", response_model=list[ContractRef])
async def proposal_contracts(request: Request, proposal_id: str) -> list[ContractRef]:
    pool, cache = pool_of(request), cache_of(request)

    async def make() -> list[ContractRef]:
        found = await rows(pool, "v2_proposal_contracts", proposal_id, 24)
        return [ContractRef.model_validate(r) for r in found]

    return await cache.get(f"proposal_contracts:{proposal_id}", make, LONG_TTL)


@router.get("/needs", response_model=list[NeedItem])
async def needs(request: Request) -> list[NeedItem]:
    return await need_items(pool_of(request), cache_of(request))


@router.get("/needs/{need_id}", response_model=NeedDetail)
async def need(request: Request, need_id: str) -> NeedDetail:
    pool, cache = pool_of(request), cache_of(request)

    async def make() -> NeedDetail | None:
        head = await rows(pool, "v2_need", need_id)
        if not head:
            return None
        base = head[0]
        evidence, counts, tools = await asyncio.gather(
            rows(pool, "v2_need_evidence", need_id, 8),
            rows(pool, "v2_need_evidence_counts", need_id),
            rows(pool, "v2_need_tools", need_id),
        )
        scoring = base["evidence"] or {}
        return NeedDetail(
            id=base["id"],
            title=base["title"],
            category=base["category"],
            origin=base["origin"],
            status=base["status"],
            score=base["score"],
            summary=base["summary"],
            demand={
                k: float(v)
                for k, v in (base["demand"] or {}).items()
                if isinstance(v, int | float)
            },
            components=scoring.get("components", {}),
            evidence_rows=scoring.get("evidence_rows", {}),
            rfp=Rfp.model_validate(base["rfp"] or {}),
            scored_at=base["scored_at"],
            comments=base["comments"],
            evidence=[Evidence.model_validate(r) for r in evidence],
            evidence_counts=[EvidenceCount.model_validate(r) for r in counts],
            tools=[ToolRef.model_validate(r) for r in tools],
        )

    found = await cache.get(f"need:{need_id}", make, SHORT_TTL)
    if found is None:
        raise HTTPException(404, "unknown need")
    return found


@router.get("/patterns", response_model=PatternList)
async def patterns(request: Request) -> PatternList:
    pool, cache = pool_of(request), cache_of(request)
    found = await cache.get(
        "patterns", lambda: load_patterns(pool), LONG_TTL, WARM_PATIENCE
    )
    if found is None:
        return PatternList(items=[], warming=True)
    return PatternList(items=found)


async def load_repo_index(pool: asyncpg.Pool) -> list[RepoItem]:
    found = await rows(pool, "v2_repo_index")
    return [
        RepoItem.model_validate(
            {**r, "topics": r["topics"] or [], "rust_loc": r["rust_loc"] or 0}
        )
        for r in found
    ]


def repo_rank(repo: RepoItem, terms: list[str]) -> float | None:
    name = repo.full_name.lower()
    text = f"{repo.description or ''} {' '.join(repo.topics)}".lower()
    score = 0.0
    for term in terms:
        if term in name:
            score += 3 + (2 if name.split("/")[-1].startswith(term) else 0)
        elif term in text:
            score += 1
        else:
            return None
    return score


def find_repos(
    index: list[RepoItem], text: str | None, network: str | None, scope: str
) -> list[RepoItem]:
    terms = text.lower().split() if text else []
    found: list[tuple[float, RepoItem]] = []
    for repo in index:
        if scope == "soroban" and not repo.is_soroban:
            continue
        if scope == "stellar" and repo.is_soroban:
            continue
        if network and network not in repo.networks:
            continue
        rank = repo_rank(repo, terms) if terms else 0.0
        if rank is not None:
            found.append((rank, repo))
    found.sort(
        key=lambda pair: (-pair[0], -pair[1].stars, -(pair[1].window_commits or 0))
    )
    return [repo for _, repo in found]


@router.get("/repos", response_model=RepoList)
async def repos(
    request: Request,
    q: str | None = None,
    network: Literal["mainnet", "testnet"] | None = None,
    scope: Literal["soroban", "stellar", "all"] = "soroban",
    limit: int = Query(default=40, ge=1, le=200),
) -> RepoList:
    pool, cache = pool_of(request), cache_of(request)
    index = await cache.get("repo_index", lambda: load_repo_index(pool), LONG_TTL / 3)
    found = find_repos(index, q.strip() if q else None, network, scope)
    return RepoList(total=len(found), items=found[:limit])


@router.get("/repos/{owner}/{name}", response_model=RepoDetail)
async def repo(request: Request, owner: str, name: str) -> RepoDetail:
    pool, cache = pool_of(request), cache_of(request)
    full_name = f"{owner}/{name}"

    async def make() -> RepoDetail | None:
        head = await rows(pool, "v2_repo", full_name)
        if not head:
            return None
        found_proposals, found_patterns, contracts, found_needs = await asyncio.gather(
            rows(pool, "v2_neighbour_repo_proposals", full_name, 30),
            rows(pool, "v2_repo_patterns", full_name, 20),
            rows(pool, "v2_neighbour_repo_contracts", full_name, 30),
            rows(pool, "v2_repo_needs", full_name),
        )
        return RepoDetail(
            **head[0],
            proposals=[RepoProposal.model_validate(r) for r in found_proposals],
            patterns=[RepoPattern.model_validate(r) for r in found_patterns],
            contracts=[
                ContractRef.model_validate({**r, "repo": full_name}) for r in contracts
            ],
            needs=[RepoNeed.model_validate(r) for r in found_needs],
        )

    found = await cache.get(f"repo:{full_name}", make, SHORT_TTL)
    if found is None:
        raise HTTPException(404, "unknown repo")
    return found


@router.get("/chain/activity", response_model=ChainActivity)
async def chain_activity(request: Request) -> ChainActivity:
    pool, cache = pool_of(request), cache_of(request)

    async def make() -> ChainActivity:
        found = [ChainDay.model_validate(r) for r in await rows(pool, "v2_chain_days")]
        return ChainActivity(
            days=found,
            first_day=found[0].day if found else None,
            last_day=found[-1].day if found else None,
        )

    return await cache.get("chain_days", make, SHORT_TTL * 5)


@router.get("/chain/top", response_model=ChainTop)
async def chain_top(
    request: Request, limit: int = Query(default=50, ge=1, le=300)
) -> ChainTop:
    pool, cache = pool_of(request), cache_of(request)
    top = await cache.get(
        "chain_top", lambda: load_chain_top(pool), LONG_TTL, WARM_PATIENCE
    )
    if top is None:
        return ChainTop(contracts=[], edges=[], warming=True)
    return ChainTop(contracts=top.contracts[:limit], edges=top.edges[:limit])


@router.get("/contracts/{network}/{contract_id}", response_model=ContractDetail)
async def contract(request: Request, network: str, contract_id: str) -> ContractDetail:
    pool, cache = pool_of(request), cache_of(request)

    async def make() -> ContractDetail | None:
        head = await rows(pool, "v2_contract", network, contract_id)
        if not head:
            return None
        days, linked = await asyncio.gather(
            rows(pool, "v2_contract_days", network, contract_id),
            rows(pool, "v2_neighbour_contract_repos", network, contract_id, 20),
        )
        base = head[0]
        return ContractDetail(
            **{
                **base,
                "function_names": base["function_names"] or [],
                "invocations": base["invocations"] or 0,
            },
            days=[ContractDay.model_validate(d) for d in days],
            repos=[RepoRef.model_validate(r) for r in linked],
        )

    found = await cache.get(f"contract:{network}:{contract_id}", make, SHORT_TTL)
    if found is None:
        raise HTTPException(404, "unknown contract")
    return found


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request, q: str = Query(min_length=2, max_length=80)
) -> SearchResponse:
    pool, cache = pool_of(request), cache_of(request)
    text = q.strip()

    async def make() -> SearchResponse:
        found = await rows(pool, "v2_search", f"%{text}%")
        chain = (
            await rows(pool, "v2_search_contracts", f"{text}%")
            if len(text) >= 4
            else []
        )
        hits = [SearchHit.model_validate(r) for r in found]
        needle = text.lower()
        listed = cache.values.get("patterns")
        for item in listed[1] if listed else []:
            if needle in item.id.lower() or needle in item.description.lower():
                hits.append(
                    SearchHit(
                        kind="pattern",
                        id=item.id,
                        label=item.id,
                        sub=item.description[:110],
                    )
                )
        indexed = cache.values.get("repo_index")
        if indexed:
            for repo_item in find_repos(indexed[1], text, None, "all")[:8]:
                hits.append(
                    SearchHit(
                        kind="repo",
                        id=repo_item.full_name,
                        label=repo_item.full_name,
                        sub=(repo_item.description or "")[:110],
                        score=math.log1p(repo_item.stars),
                    )
                )
        hits += [
            SearchHit(
                kind="contract",
                id=f"{r['network']}/{r['contract_id']}",
                label=r["contract_id"],
                sub=f"{r['network']} contract",
            )
            for r in chain
        ]
        return SearchResponse(q=text, hits=hits)

    return await cache.get(f"search:{needle_key(text)}", make, SHORT_TTL)


def needle_key(text: str) -> str:
    return text.lower()


@router.get("/comments", response_model=list[Comment])
async def comments(request: Request, target_kind: str, target_id: str) -> list[Comment]:
    found = await rows(pool_of(request), "comments_list", target_kind, target_id)
    return [Comment.model_validate(r) for r in found]


@router.post("/comments", response_model=Comment)
async def add_comment(request: Request, comment: CommentCreate) -> Comment:
    found = await rows(
        pool_of(request),
        "comments_add",
        comment.target_kind,
        comment.target_id,
        comment.author,
        comment.body,
    )
    return Comment.model_validate(found[0])


async def warm_chain(pool: asyncpg.Pool, cache: Cache) -> None:
    top = await cache.get("chain_top", lambda: load_chain_top(pool), LONG_TTL)
    await cache.get("chain_graph", lambda: load_chain_graph(pool, top), LONG_TTL)


async def warm(app: Any) -> None:
    pool, cache = app.state.pool, app.state.v2
    steps = [
        cache.get("graph", lambda: load_graph(pool), GRAPH_TTL),
        cache.get("repo_index", lambda: load_repo_index(pool), LONG_TTL / 3),
        cache.get("wrapped", lambda: build_wrapped(pool, cache), SHORT_TTL),
        warm_chain(pool, cache),
        cache.get("patterns", lambda: load_patterns(pool), LONG_TTL),
    ]
    for step in steps:
        try:
            await step
        except Exception:
            continue
