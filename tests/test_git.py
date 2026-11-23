from state_of_soroban.extract.git import login_of, parse_log, target_path

RAW = (
    "\x1eabc123\x1fAda\x1f12+ada@users.noreply.github.com\x1f2026-03-01T10:00:00+00:00"
    "\x1fp1 p2\x1ffix: archived entries\n\nbody\x1f\n"
    "M\tsrc/lib.rs\nA\tassets/logo.png\nR100\tsrc/old/mod.rs\tsrc/new/mod.rs\n"
)


def test_a_log_record_becomes_a_commit_with_its_file_stats():
    commit = parse_log(RAW)[0]

    assert commit.sha == "abc123" and commit.parents == 2
    assert commit.author_login == "ada"
    assert [f.status for f in commit.files] == ["M", "A", "R"]
    assert commit.files[2].path == "src/new/mod.rs"
    assert commit.files[2].previous_path == "src/old/mod.rs"


def test_only_noreply_emails_reveal_a_login():
    assert login_of("ada@example.com") is None
    assert login_of("ada@users.noreply.github.com") == "ada"
    assert target_path("a.rs => b.rs") == ("b.rs", "a.rs")
