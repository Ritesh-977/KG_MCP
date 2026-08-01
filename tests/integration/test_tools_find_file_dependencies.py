"""find_file_dependencies tool integration test."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_find_deps_returns_imported_by(adapter, fresh_graph_id) -> None:
    await adapter._run_write(
        "CREATE (r:Repository {graph_id: $gid}) "
        "-[:CONTAINS]->(auth:File {graph_id: $gid, path: 'auth.py', language: 'py', deleted: false}), "
        "(r)-[:CONTAINS]->(us:File {graph_id: $gid, path: 'user_service.py', language: 'py', deleted: false}) "
        "WITH r, auth, us MERGE (us)-[:IMPORTS]->(auth)",
        gid=fresh_graph_id,
    )
    from codegraph.models.tools import FindFileDependenciesArgs
    from codegraph.tools.find_file_dependencies import find_file_dependencies

    res = await find_file_dependencies(
        adapter, FindFileDependenciesArgs(graph_id=fresh_graph_id, file_path="auth.py")
    )
    paths = [e.path for e in res.imported_by]
    assert "user_service.py" in paths
