import pytest

from state_of_soroban.catalog import load_catalog
from state_of_soroban.config import ROOT
from state_of_soroban.runner import order, select
from state_of_soroban.workflow import Stage, load_workflow

WORKFLOW = ROOT / "workflow" / "workflow.yaml"


def stage(name: str, *needs: str) -> Stage:
    return Stage(id=name, uses=f"x.{name}", needs=list(needs))


def test_the_committed_workflow_and_catalog_are_valid_and_linked():
    workflow = load_workflow(WORKFLOW)
    catalog = load_catalog(workflow)

    assert workflow.window.end >= workflow.window.start
    assert {p.id for p in catalog.patterns} >= {
        item.id for proposal in catalog.proposals for item in proposal.patterns
    }


def test_stages_run_after_the_stages_they_need():
    stages = [stage("graph", "clone"), stage("clone", "discover"), stage("discover")]

    assert [s.id for s in order(stages)] == ["discover", "clone", "graph"]


def test_a_stage_cycle_is_refused():
    with pytest.raises(ValueError, match="cycle"):
        order([stage("a", "b"), stage("b", "a")])


def test_select_narrows_the_run_and_rejects_unknown_stages():
    stages = [stage("a"), stage("b", "a"), stage("c", "b")]

    assert [s.id for s in select(stages, [], [], "b")] == ["b", "c"]
    assert [s.id for s in select(stages, ["c"], [], None)] == ["c"]
    assert [s.id for s in select(stages, [], ["b"], None)] == ["a", "c"]
    with pytest.raises(ValueError, match="unknown stage"):
        select(stages, ["nope"], [], None)
