"""git ops — pure-logic URL parsing; live clone is slow-marked."""

from __future__ import annotations

from pathlib import Path

import pytest

from codegraph.ingestion.git import local_path_for, repo_slug_from_url


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/owner/name.git", "owner/name"),
    ("https://github.com/owner/name", "owner/name"),
    ("git@github.com:owner/name.git", "owner/name"),
    ("https://gitlab.com/group/sub/proj.git", "group/sub/proj"),
])
def test_slug_from_url(url: str, expected: str) -> None:
    assert repo_slug_from_url(url) == expected


def test_local_path_uses_repos_dir_and_safe_name() -> None:
    p = local_path_for("https://github.com/owner/name.git", Path("./repos"))
    assert p.parent == Path("./repos").resolve()
    assert "owner" in p.name and "name" in p.name
