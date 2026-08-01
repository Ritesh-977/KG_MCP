"""find_file_dependencies tool — the flagship: what depends on / is depended on by a file."""

from __future__ import annotations

from codegraph.models.tools import (
    DependencyEntry,
    ExternalSymbolEntry,
    FindFileDependenciesArgs,
    FindFileDependenciesResult,
)
from codegraph.repo.port import CodeGraphRepository


async def find_file_dependencies(
    repo: CodeGraphRepository, args: FindFileDependenciesArgs
) -> FindFileDependenciesResult:
    d = await repo.find_file_dependencies(
        graph_id=args.graph_id,
        file_path=args.file_path,
        direction=args.direction,
        max_hops=args.max_hops,
    )
    return FindFileDependenciesResult(
        file=d["file"],
        imported_by=[DependencyEntry(**e) for e in d.get("imported_by", [])],
        imports=[DependencyEntry(**e) for e in d.get("imports", [])],
        callers=[DependencyEntry(**e) for e in d.get("callers", [])],
        calls=[DependencyEntry(**e) for e in d.get("calls", [])],
        external_symbols=[ExternalSymbolEntry(**e) for e in d.get("external_symbols", [])],
        truncated=d.get("truncated", False),
        hint=d.get("hint"),
    )
