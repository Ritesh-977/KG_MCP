"""Filesystem walker — yields FileEntry for each parseable file.

Respects .gitignore via pathspec. Skips common noise directories.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pathspec

_EXT_LANG = {
    ".py": "py",
    ".js": "js", ".mjs": "js", ".cjs": "js",
    ".ts": "ts", ".tsx": "tsx", ".jsx": "js",
}

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


@dataclass(frozen=True)
class FileEntry:
    path: str       # repo-relative POSIX
    abspath: Path
    language: str   # "py"|"js"|"ts"|"tsx"|"other"


def _load_gitignore(root: Path) -> pathspec.PathSpec | None:
    gi = root / ".gitignore"
    if not gi.exists():
        return None
    with gi.open(encoding="utf-8") as f:
        return pathspec.PathSpec.from_lines("gitwildmatch", f)


def walk_repo(root: Path) -> list[FileEntry]:
    spec = _load_gitignore(root)
    root = root.resolve()
    out: list[FileEntry] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            abspath = Path(dirpath) / fn
            rel = abspath.relative_to(root)
            rel_posix = rel.as_posix()
            if spec and spec.match_file(rel_posix):
                continue
            ext = rel.suffix.lower()
            lang = _EXT_LANG.get(ext, "other")
            if lang == "other":
                continue
            out.append(FileEntry(path=rel_posix, abspath=abspath, language=lang))
    return out
