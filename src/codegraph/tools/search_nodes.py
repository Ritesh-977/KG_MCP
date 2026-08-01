"""search_nodes tool — find functions/files by name."""

from __future__ import annotations

from codegraph.models.tools import SearchHit, SearchNodesArgs, SearchNodesResult
from codegraph.repo.port import CodeGraphRepository


async def search_nodes(
    repo: CodeGraphRepository, args: SearchNodesArgs
) -> SearchNodesResult:
    rows = await repo.search_nodes(
        graph_id=args.graph_id,
        query=args.query,
        kind=args.kind,
        limit=args.limit,
    )
    return SearchNodesResult(hits=[SearchHit(**r) for r in rows])
