"""Tool model validation — pydantic DTOs for MCP tools."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codegraph.models.tools import (
    FindFileDependenciesArgs,
    GetNodeDetailArgs,
    GetRepoStructureArgs,
    InitRepositoryNodeArgs,
    SearchNodesArgs,
)


def test_init_repo_args_validates_graph_id() -> None:
    args = InitRepositoryNodeArgs(graph_id="owner/name")
    assert args.graph_id == "owner/name"


def test_init_repo_args_rejects_bad_graph_id() -> None:
    with pytest.raises(ValidationError):
        InitRepositoryNodeArgs(graph_id="bad graph")


def test_get_repo_structure_defaults() -> None:
    args = GetRepoStructureArgs(graph_id="o/n")
    assert args.path == ""
    assert args.limit == 200


def test_get_repo_structure_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        GetRepoStructureArgs(graph_id="o/n", limit=0)
    with pytest.raises(ValidationError):
        GetRepoStructureArgs(graph_id="o/n", limit=1001)


def test_find_file_deps_args_defaults() -> None:
    args = FindFileDependenciesArgs(graph_id="o/n", file_path="src/auth.py")
    assert args.direction == "both"
    assert args.max_hops == 2


def test_find_file_deps_args_max_hops_bounds() -> None:
    with pytest.raises(ValidationError):
        FindFileDependenciesArgs(graph_id="o/n", file_path="x.py", max_hops=5)


def test_search_nodes_args_requires_query() -> None:
    with pytest.raises(ValidationError):
        SearchNodesArgs(graph_id="o/n", query="")


def test_get_node_detail_args() -> None:
    args = GetNodeDetailArgs(graph_id="o/n", node_id="abc123")
    assert args.node_id == "abc123"
