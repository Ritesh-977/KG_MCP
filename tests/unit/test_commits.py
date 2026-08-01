"""git log output parser — pure logic."""

from __future__ import annotations

from codegraph.ingestion.commits import parse_log_output

_LOG = """abc123|Alice|2026-07-20T10:00:00+00:00
src/auth.py
src/main.py

def456|Bob|2026-07-19T09:00:00+00:00
README.md
"""


def test_parses_per_file_last_author() -> None:
    info = parse_log_output(_LOG)
    assert info["src/auth.py"].last_author == "Alice"
    assert info["src/main.py"].last_author == "Alice"
    assert info["README.md"].last_author == "Bob"


def test_last_commit_sha_captured() -> None:
    info = parse_log_output(_LOG)
    assert info["src/auth.py"].last_commit_sha == "abc123"
    assert info["README.md"].last_commit_sha == "def456"


def test_empty_log_returns_empty() -> None:
    assert parse_log_output("") == {}
