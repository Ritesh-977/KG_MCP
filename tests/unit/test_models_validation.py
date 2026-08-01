"""Unit tests for pydantic model validation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from codegraph.models.common import FilePath, GraphId, RepoSlug


class _Wrap(BaseModel):
    gid: GraphId
    slug: RepoSlug
    path: FilePath


def test_graph_id_accepts_owner_slash_name() -> None:
    w = _Wrap(gid="owner/name", slug="owner/name", path="src/auth.py")
    assert w.gid == "owner/name"


def test_graph_id_rejects_spaces() -> None:
    with pytest.raises(ValidationError):
        _Wrap(gid="owner name", slug="o/n", path="x.py")


def test_filepath_normalizes_backslashes_to_posix() -> None:
    w = _Wrap(gid="o/n", slug="o/n", path="src\\auth.py")
    assert w.path == "src/auth.py"


def test_filepath_strips_leading_dot_slash() -> None:
    w = _Wrap(gid="o/n", slug="o/n", path="./src/auth.py")
    assert w.path == "src/auth.py"
