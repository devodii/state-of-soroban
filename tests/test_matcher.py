from pathlib import Path

from state_of_soroban.catalog import Match, Pattern
from state_of_soroban.extract.matcher import run_patterns
from state_of_soroban.extract.rust import parse_rust

FIXTURE = Path(__file__).parent / "fixtures" / "token.rs"

PATTERNS = [
    Pattern(
        id="auth.require_auth",
        category="auth",
        description="a caller is authorised",
        match=Match(kind="regex", regex=r"\.require_auth\(\)"),
    ),
    Pattern(
        id="error.unwrap_call",
        category="error",
        description="an unwrap aborts",
        match=Match(kind="regex", regex=r"\.unwrap\(\)"),
    ),
    Pattern(
        id="test.env_default",
        category="test",
        description="a default test environment",
        match=Match(kind="regex", regex=r"Env::default\(\)"),
    ),
]


def found():
    parsed = parse_rust("src/lib.rs", FIXTURE.read_bytes())
    hits = run_patterns(PATTERNS, parsed)
    return {hit.pattern for hit in hits}, hits


def test_the_matcher_finds_patterns_in_the_fixture():
    ids, _ = found()

    assert {"auth.require_auth", "error.unwrap_call"} <= ids


def test_comments_never_match_and_tests_are_flagged():
    _, hits = found()

    assert not any(h.pattern == "auth.require_auth" and h.in_test for h in hits)
    assert any(h.pattern == "test.env_default" and h.in_test for h in hits)
