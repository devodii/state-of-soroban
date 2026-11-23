from pathlib import Path

from state_of_soroban.catalog import load_catalog
from state_of_soroban.config import ROOT
from state_of_soroban.extract.matcher import run_patterns
from state_of_soroban.extract.rust import parse_rust
from state_of_soroban.workflow import load_workflow

FIXTURE = Path(__file__).parent / "fixtures" / "token.rs"


def found():
    catalog = load_catalog(load_workflow(ROOT / "workflow" / "workflow.yaml"))
    parsed = parse_rust("src/lib.rs", FIXTURE.read_bytes())
    hits = run_patterns(catalog.patterns, parsed)
    return {hit.pattern for hit in hits}, hits


def test_the_catalog_finds_the_boilerplate_in_the_fixture():
    ids, _ = found()

    assert {
        "auth.require_auth",
        "auth.admin_guard",
        "ttl.persistent_bump",
        "storage.datakey_enum",
        "error.contracterror_enum",
        "init.initialize_fn",
        "init.reinit_guard",
        "error.unwrap_call",
        "test.env_default",
        "auth.mock_all_auths",
    } <= ids


def test_comments_never_match_and_tests_are_flagged():
    ids, hits = found()

    assert "init.unguarded" not in ids
    assert any(h.pattern == "test.env_default" and h.in_test for h in hits)
    assert not any(h.pattern == "auth.require_auth" and h.in_test for h in hits)
