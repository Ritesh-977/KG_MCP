"""get_repo_structure tool integration test."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_structure_lists_files(adapter, fresh_graph_id) -> None:
    await adapter._run_write(
        "CREATE (r:Repository {graph_id: $gid}) "
        "-[:CONTAINS]->(f1:File {graph_id: $gid, path: 'src/a.py', language: 'py', deleted: false}), "
        "(r)-[:CONTAINS]->(f2:File {graph_id: $gid, path: 'README.md', language: 'other', deleted: false})",
        gid=fresh_graph_id,
    )
    from codegraph.models.tools import GetRepoStructureArgs
    from codegraph.tools.get_repo_structure import get_repo_structure

    res = await get_repo_structure(
        adapter, GetRepoStructureArgs(graph_id=fresh_graph_id, path="src")
    )
    names = [e.name for e in res.entries]
    assert "a.py" in names
