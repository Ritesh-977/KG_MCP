"""list_repos tool integration test."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_list_repos_returns_ingested(adapter, fresh_graph_id) -> None:
    await adapter._run_write(
        "CREATE (r:Repository {graph_id: $gid, name: $gid, url: $url, default_branch: 'main'})",
        gid=fresh_graph_id, url="https://github.com/test/x",
    )
    from codegraph.tools.list_repos import list_repos

    res = await list_repos(adapter)
    gids = [r.graph_id for r in res.repos]
    assert fresh_graph_id in gids
