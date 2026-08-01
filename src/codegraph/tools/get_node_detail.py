"""get_node_detail tool — deep detail on one node."""

from __future__ import annotations

from codegraph.models.tools import GetNodeDetailArgs, GetNodeDetailResult
from codegraph.repo.port import CodeGraphRepository


async def get_node_detail(
    repo: CodeGraphRepository, args: GetNodeDetailArgs
) -> GetNodeDetailResult:
    d = await repo.get_node_detail(graph_id=args.graph_id, node_id=args.node_id)
    if d is None:
        raise ValueError(
            f"Node '{args.node_id}' not found in graph '{args.graph_id}'. "
            f"Call search_nodes first to get a valid node id."
        )
    return GetNodeDetailResult(**d)
