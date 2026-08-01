"""search_nodes tool integration test."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_search_finds_function_by_name(adapter, fresh_graph_id) -> None:
    await adapter._run_write(
        "CREATE (:Repository {graph_id: $gid}) "
        "-[:CONTAINS]->(:File {graph_id: $gid, path: 'a.py', language: 'py', deleted: false}) "
        "-[:DEFINES]->(:Function {graph_id: $gid, qualified_name: 'authenticate', name: 'authenticate', kind: 'function'})",
        gid=fresh_graph_id,
    )
    from codegraph.models.tools import SearchNodesArgs
    from codegraph.tools.search_nodes import search_nodes

    res = await search_nodes(
        adapter, SearchNodesArgs(graph_id=fresh_graph_id, query="auth")
    )
    names = [h.name for h in res.hits]
    assert "authenticate" in names
