"""Git operations: clone/fetch + default-branch resolution.

Uses GitPython. The clone itself is network I/O — unit tests cover pure URL parsing;
integration is exercised end-to-end via the ingest CLI against a fixture dir.
"""

from __future__ import annotations

import re
from pathlib import Path

from git import Repo

_URL_RE = re.compile(r"(?:https://|git@)(?P<host>[^/:]+)[:/](?P<path>.+?)(?:\.git)?$")


def repo_slug_from_url(url: str) -> str:
    m = _URL_RE.match(url.strip())
    if not m:
        raise ValueError(f"unparseable repo URL: {url!r}")
    return m.group("path")


def local_path_for(url: str, repos_dir: Path) -> Path:
    slug = repo_slug_from_url(url)
    safe = slug.replace("/", "__")
    return (repos_dir / safe).resolve()


def clone_or_fetch(url: str, dest: Path, branch: str | None, depth: int) -> str:
    """Clone (or fetch+reset) into dest; return the resolved default branch name."""
    if dest.exists() and (dest / ".git").exists():
        repo = Repo(str(dest))
        repo.remotes.origin.fetch()
        br = branch or _detect_default(repo)
        repo.git.checkout(br)
        repo.git.reset("--hard", f"origin/{br}")
        return br
    if branch:
        repo = Repo.clone_from(url, str(dest), depth=depth, branch=branch)
        return branch
    repo = Repo.clone_from(url, str(dest), depth=depth)
    return _detect_default(repo)


def _detect_default(repo: Repo) -> str:
    try:
        return repo.head.ref.name
    except Exception:
        try:
            out: str = str(repo.git.symbolic_ref("refs/remotes/origin/HEAD"))
            return out.replace("refs/remotes/origin/", "")
        except Exception:
            return "main"
