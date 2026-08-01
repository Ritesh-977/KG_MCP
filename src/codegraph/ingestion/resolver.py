"""Pure-logic import-path → repo-rel file path resolution. No I/O.

Conservative: returns None for anything that cannot be resolved to a file
that exists in `known_files`. Callers turn unresolved imports into :Symbol leaves.
"""

from __future__ import annotations

import os


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _try_candidates(candidates: list[str], known: set[str]) -> str | None:
    for c in candidates:
        if c in known:
            return c
    return None


def resolve_python_import(module: str, current_file: str, known_files: set[str]) -> str | None:
    """Resolve `from a.b import c` / `import a.b` → repo-rel path or None.

    Handles: absolute `a.b.c`, relative `.b`, `..b`.
    """
    if not module:
        return None
    # Relative import
    if module.startswith("."):
        dots = len(module) - len(module.lstrip("."))
        rel = module.lstrip(".")
        base_dir = os.path.dirname(current_file)
        for _ in range(dots - 1):
            base_dir = os.path.dirname(base_dir)
        if rel:
            rel_path = _posix(os.path.normpath(os.path.join(base_dir, rel.replace(".", "/"))))
        else:
            rel_path = _posix(base_dir)
        return _try_candidates(
            [f"{rel_path}.py", f"{rel_path}/__init__.py"], known_files
        )
    # Absolute — try direct path, then suffix match against known files
    # (handles src-layout where `pkg.x` maps to `src/pkg/x.py`).
    parts = module.split(".")
    base = "/".join(parts)
    direct = _try_candidates([f"{base}.py", f"{base}/__init__.py"], known_files)
    if direct is not None:
        return direct
    for suffix in (f"/{base}.py", f"/{base}/__init__.py"):
        for f in known_files:
            if f.endswith(suffix):
                return f
    return None


def resolve_js_import(spec: str, current_file: str, known_files: set[str]) -> str | None:
    """Resolve a JS/TS import spec → repo-rel path or None. Only relative specs resolve."""
    if not spec.startswith("."):
        return None
    base_dir = os.path.dirname(current_file)
    rel = _posix(os.path.normpath(os.path.join(base_dir, spec)))
    return _try_candidates(
        [
            f"{rel}.js", f"{rel}.ts", f"{rel}.tsx", f"{rel}.jsx",
            f"{rel}/index.js", f"{rel}/index.ts", f"{rel}/index.tsx", f"{rel}/index.jsx",
        ],
        known_files,
    )
