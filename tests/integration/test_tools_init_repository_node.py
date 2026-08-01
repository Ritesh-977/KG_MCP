"""init_repository_node tool integration test."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_init_repo_returns_counts(adapter, fresh_graph_id) -> None:
    await adapter._run_write(
        "CREATE (r:Repository {graph_id: $gid, name: $gid, url: $u, default_branch: 'main'}) "
        "-[:CONTAINS]->(f:File {graph_id: $gid, path: 'a.py', language: 'py', deleted: false}) "
        "-[:DEFINES]->(fn:Function {graph_id: $gid, qualified_name: 'foo', name: 'foo', kind: 'function'})",
        gid=fresh_graph_id, u="https://github.com/test/x",
    )
    from codegraph.models.tools import InitRepositoryNodeArgs
    from codegraph.tools.init_repository_node import init_repository_node

    res = await init_repository_node(adapter, InitRepositoryNodeArgs(graph_id=fresh_graph_id))
    assert res.file_count == 1
    assert res.function_count == 1


async def test_init_repo_error_for_unknown(adapter, fresh_graph_id) -> None:
    from codegraph.models.tools import InitRepositoryNodeArgs
    from codegraph.tools.init_repository_node import init_repository_node

    with pytest.raises(ValueError, match="not ingested"):
        await init_repository_node(adapter, InitRepositoryNodeArgs(graph_id="no/such"))
