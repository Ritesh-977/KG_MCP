"""One-pass git log → per-file last author/date/sha."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from git import Repo


@dataclass(frozen=True)
class CommitInfo:
    last_commit_sha: str
    last_author: str
    last_commit_at: str


def parse_log_output(text: str) -> dict[str, CommitInfo]:
    """Parse `git log --format='%H|%an|%aI' --name-only` output."""
    out: dict[str, CommitInfo] = {}
    blocks = text.strip().split("\n\n") if text.strip() else []
    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue
        header = lines[0].split("|", maxsplit=2)
        if len(header) != 3:
            continue
        sha, author, date = header
        for path in lines[1:]:
            p = path.strip()
            if p and p not in out:  # first occurrence = most recent
                out[p] = CommitInfo(last_commit_sha=sha, last_author=author, last_commit_at=date)
    return out


def collect_commits(repo_root: Path) -> dict[str, CommitInfo]:
    repo = Repo(str(repo_root))
    out = repo.git.log("--format=%H|%an|%aI", "--name-only")
    return parse_log_output(out)
