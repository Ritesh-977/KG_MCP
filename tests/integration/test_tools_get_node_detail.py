"""get_node_detail tool integration test."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_get_node_detail_returns_lines(adapter, fresh_graph_id) -> None:
    rows = await adapter._run_write(
        "CREATE (fn:Function {graph_id: $gid, qualified_name: 'foo', name: 'foo', "
        "kind: 'function', start_line: 3, end_line: 5, path: 'a.py'}) "
        "RETURN elementId(fn) AS id",
        gid=fresh_graph_id,
    )
    nid = rows[0]["id"]
    from codegraph.models.tools import GetNodeDetailArgs
    from codegraph.tools.get_node_detail import get_node_detail

    res = await get_node_detail(
        adapter, GetNodeDetailArgs(graph_id=fresh_graph_id, node_id=nid)
    )
    assert res.start_line == 3
    assert res.end_line == 5
