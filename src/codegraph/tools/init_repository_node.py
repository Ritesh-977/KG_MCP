"""init_repository_node tool — confirm a repo's graph exists, return counts."""

from __future__ import annotations

from codegraph.models.tools import InitRepositoryNodeArgs, InitRepositoryNodeResult
from codegraph.repo.port import CodeGraphRepository


async def init_repository_node(
    repo: CodeGraphRepository, args: InitRepositoryNodeArgs
) -> InitRepositoryNodeResult:
    info = await repo.get_repo_info(graph_id=args.graph_id)
    if info is None:
        raise ValueError(
            f"Repository '{args.graph_id}' not ingested. Call `list_repos` to see "
            f"available graphs, or run: python -m codegraph ingest "
            f"https://github.com/{args.graph_id}"
        )
    return InitRepositoryNodeResult(
        graph_id=info["graph_id"],
        name=info["name"],
        url=info["url"],
        file_count=int(info.get("file_count", 0)),
        function_count=int(info.get("function_count", 0)),
    )
