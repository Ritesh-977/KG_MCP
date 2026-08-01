"""Adapter smoke: connect, apply migrations, write+read one node, soft-cleanup."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_adapter_connects_and_applies_migrations(adapter) -> None:  # type: ignore[no-untyped-def]
    # If we got here, connect + apply_migrations succeeded in the fixture.
    assert adapter is not None


@pytest.mark.asyncio
async def test_adapter_writes_and_reads_node(adapter, fresh_graph_id) -> None:  # type: ignore[no-untyped-def]
    rows = await adapter._run_write(
        "CREATE (r:Repository {graph_id: $gid, name: $name, url: $url}) "
        "RETURN r.graph_id AS gid",
        gid=fresh_graph_id,
        name="o/n",
        url="https://github.com/o/n",
    )
    assert rows and rows[0]["gid"] == fresh_graph_id

    read = await adapter._run_read(
        "MATCH (r:Repository {graph_id: $gid}) RETURN r.name AS name",
        gid=fresh_graph_id,
    )
    assert read and read[0]["name"] == "o/n"


@pytest.mark.asyncio
async def test_list_repos_returns_ingested(adapter, fresh_graph_id) -> None:  # type: ignore[no-untyped-def]
    await adapter._run_write(
        "CREATE (r:Repository {graph_id: $gid, name: $name, url: $url, "
        "default_branch: 'main', ingested_at: datetime()})",
        gid=fresh_graph_id,
        name="o/n",
        url="https://github.com/o/n",
    )
    repos = await adapter.list_repos()
    gids = [r["graph_id"] for r in repos]
    assert fresh_graph_id in gids


@pytest.mark.asyncio
async def test_get_repo_info_returns_counts(adapter, fresh_graph_id) -> None:  # type: ignore[no-untyped-def]
    await adapter._run_write(
        "CREATE (r:Repository {graph_id: $gid, name: $gid, url: $u, default_branch: 'main'}) "
        "-[:CONTAINS]->(f:File {graph_id: $gid, path: 'a.py', language: 'py', deleted: false}) "
        "-[:DEFINES]->(fn:Function {graph_id: $gid, qualified_name: 'foo', name: 'foo', "
        "kind: 'function'})",
        gid=fresh_graph_id,
        u="https://github.com/test/x",
    )
    info = await adapter.get_repo_info(graph_id=fresh_graph_id)
    assert info is not None
    assert int(info["file_count"]) == 1
    assert int(info["function_count"]) == 1


@pytest.mark.asyncio
async def test_get_repo_info_returns_none_for_unknown(adapter, fresh_graph_id) -> None:  # type: ignore[no-untyped-def]
    info = await adapter.get_repo_info(graph_id="no/such/repo")
    assert info is None
