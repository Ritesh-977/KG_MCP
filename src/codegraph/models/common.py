"""Common pydantic types: GraphId, RepoSlug, FilePath."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator

_GRAPH_ID_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def _normalize_filepath(v: str) -> str:
    """Normalize to repo-relative POSIX: backslashes → forward slashes, strip leading ./."""
    out = v.replace("\\", "/")
    if out.startswith("./"):
        out = out[2:]
    return out


def _validate_graph_id(v: str) -> str:
    if not v or not _GRAPH_ID_RE.match(v):
        raise ValueError(f"graph_id must match {_GRAPH_ID_RE.pattern}; got {v!r}")
    return v


GraphId = Annotated[str, BeforeValidator(_validate_graph_id)]
RepoSlug = Annotated[str, BeforeValidator(_validate_graph_id)]
FilePath = Annotated[str, BeforeValidator(_normalize_filepath)]
