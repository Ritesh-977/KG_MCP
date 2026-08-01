"""Walker — filesystem walk with .gitignore + skip rules."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from codegraph.ingestion.walker import walk_repo

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "py_repo"


def test_walk_returns_py_files() -> None:
    entries = walk_repo(_FIXTURE)
    paths = sorted(e.path for e in entries)
    assert "auth.py" in paths
    assert "main.py" in paths


def test_walk_paths_are_repo_relative_posix() -> None:
    entries = walk_repo(_FIXTURE)
    for e in entries:
        assert "\\" not in e.path
        assert not e.path.startswith("/")


def test_walk_classifies_language() -> None:
    entries = walk_repo(_FIXTURE)
    by_path = {e.path: e.language for e in entries}
    assert by_path["auth.py"] == "py"
    assert by_path["main.py"] == "py"


def test_walk_skips_gitignore_and_caches() -> None:
    entries = walk_repo(_FIXTURE)
    paths = [e.path for e in entries]
    assert not any(p.startswith("__pycache__") for p in paths)
    assert not any(p.startswith(".venv") for p in paths)
    # Verify pathspec actually exercises .gitignore (not just _SKIP_DIRS):
    # secrets.env is NOT in _SKIP_DIRS — only .gitignore excludes it.
    assert "secrets.env" not in paths


def test_walk_skips_dot_git() -> None:
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, ".git", "refs"))
        with open(os.path.join(td, "a.py"), "w") as f:
            f.write("x = 1\n")
        entries = walk_repo(Path(td))
        paths = [e.path for e in entries]
        assert "a.py" in paths
        assert not any(p.startswith(".git") for p in paths)
