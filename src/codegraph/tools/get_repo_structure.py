"""get_repo_structure tool — tiered tree view under a path."""

from __future__ import annotations

from codegraph.models.tools import (
    GetRepoStructureArgs,
    GetRepoStructureResult,
    StructureEntry,
)
from codegraph.repo.port import CodeGraphRepository


async def get_repo_structure(
    repo: CodeGraphRepository, args: GetRepoStructureArgs
) -> GetRepoStructureResult:
    d = await repo.get_repo_structure(
        graph_id=args.graph_id, path=args.path, limit=args.limit
    )
    return GetRepoStructureResult(
        path=d["path"],
        truncated=d.get("truncated", False),
        entries=[StructureEntry(**e) for e in d["entries"]],
    )
