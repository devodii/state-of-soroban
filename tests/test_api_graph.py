from state_of_soroban.api_app import build_graph, select_ecosystem


def node(id_: str, kind: str, label: str, **extra):
    return {
        "id": id_,
        "kind": kind,
        "label": label,
        "props": {},
        "stars": extra.get("stars"),
        "pushed_at": None,
        "networks": extra.get("networks"),
        "language": None,
        "proposal_score": extra.get("score"),
        "status": None,
        "origin": None,
        "live": None,
    }


def edge(src: str, dst: str, kind: str, weight: float):
    return {"src": src, "dst": dst, "kind": kind, "weight": weight}


def test_selection_keeps_proposals_and_caps_repos_by_reuse():
    nodes = [
        node("proposal:p", "proposal", "p", score=40),
        node("repo:a/a", "repo", "a/a", networks=["mainnet"], stars=5),
        node("repo:b/b", "repo", "b/b", networks=["testnet"], stars=1),
        node("contract:mainnet:C1", "contract", "C1"),
    ]
    edges = [
        edge("repo:a/a", "proposal:p", "hand_rolls", 9),
        edge("repo:b/b", "proposal:p", "hand_rolls", 1),
        edge("repo:a/a", "contract:mainnet:C1", "deploys", 3),
    ]
    graph = build_graph(nodes, edges)
    shown = select_ecosystem(graph, 50, "mainnet", None)
    ids = {n.id for n in shown.nodes}
    assert "proposal:p" in ids
    assert "repo:a/a" in ids
    assert "repo:b/b" not in ids
    assert all(e.src in ids and e.dst in ids for e in shown.edges)
