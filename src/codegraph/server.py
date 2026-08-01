"""FastMCP server — registers read-only tools against a Neo4j-backed repository.

NOTE: This module intentionally does NOT use `from __future__ import annotations`.
The `mcp dev` Inspector loads server.py via importlib without registering it in
sys.modules first; with PEP 563 string annotations, @dataclass would fail to
resolve type hints.
"""

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.session import ServerSession
from mcp.types import CallToolResult, TextContent

from codegraph.config import Settings
from codegraph.logging_setup import setup_logging
from codegraph.models.tools import (
    FindFileDependenciesArgs,
    GetNodeDetailArgs,
    GetRepoStructureArgs,
    InitRepositoryNodeArgs,
    SearchNodesArgs,
)
from codegraph.repo.neo4j_adapter import Neo4jAdapter


@dataclass
class AppState:
    adapter: Neo4jAdapter


# Module-level handle to the active AppState. Set by the lifespan so resource
# functions (which FastMCP does not pass a ctx to) can reach the adapter.
_ACTIVE_STATE: AppState | None = None


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppState]:
    global _ACTIVE_STATE
    settings = Settings()
    setup_logging(settings.log_level)
    adapter = Neo4jAdapter.from_settings(settings)
    try:
        await adapter.connect()
        await adapter.apply_migrations()
    except Exception as ex:
        with contextlib.suppress(Exception):
            await adapter.close()
        raise RuntimeError(f"failed to initialize codegraph backend: {ex}") from ex
    state = AppState(adapter=adapter)
    _ACTIVE_STATE = state
    try:
        yield state
    finally:
        _ACTIVE_STATE = None
        with contextlib.suppress(Exception):
            await adapter.close()


def _state() -> AppState:
    """Return the active AppState, or raise if the server has not started yet."""
    if _ACTIVE_STATE is None:
        raise RuntimeError("codegraph server has not started — AppState unavailable.")
    return _ACTIVE_STATE


mcp: FastMCP = FastMCP(
    name="codegraph",
    instructions=(
        "Code dependency graph MCP server. Always: (1) call list_repos first to "
        "see available graphs; (2) call init_repository_node with a graph_id to "
        "confirm a repo exists and get file/function counts; (3) use search_nodes "
        "to find files/functions by name before calling find_file_dependencies."
    ),
    lifespan=app_lifespan,
)


def get_state(ctx: Any) -> AppState:
    """Pull AppState from a FastMCP Context's lifespan context."""
    return ctx.request_context.lifespan_context  # type: ignore[no-any-return]


@mcp.tool()
async def list_repos(
    ctx: Context[ServerSession, AppState],
) -> CallToolResult:
    """List all ingested repositories in the graph database."""
    from codegraph.tools.list_repos import list_repos as _impl

    state = get_state(ctx)
    try:
        result = await _impl(state.adapter)
    except Exception as ex:
        raise ToolError(f"Failed to list repos: {ex}. Check Neo4j is running.") from ex
    lines = [f"{len(result.repos)} repo(s) available:"]
    for r in result.repos:
        lines.append(f"  - graph_id: {r.graph_id}  (name: {r.name}, branch: {r.default_branch})")
    summary = (
        "\n".join(lines)
        if result.repos
        else "No repos ingested. Run: python -m codegraph ingest <github-url>"
    )
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result.model_dump(),
    )


@mcp.tool()
async def init_repository_node(
    ctx: Context[ServerSession, AppState],
    graph_id: str,
) -> CallToolResult:
    """Confirm a repository's graph exists and return file/function counts."""
    from codegraph.tools.init_repository_node import init_repository_node as _impl

    state = get_state(ctx)
    try:
        result = await _impl(state.adapter, InitRepositoryNodeArgs(graph_id=graph_id))
    except ValueError as ex:
        raise ToolError(str(ex)) from ex
    except Exception as ex:
        raise ToolError(f"Failed to query repo '{graph_id}': {ex}. Check Neo4j is running.") from ex
    summary = f"Repository '{result.graph_id}': {result.file_count} files, {result.function_count} functions (url: {result.url})"
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result.model_dump(),
    )


@mcp.tool()
async def get_repo_structure(
    ctx: Context[ServerSession, AppState],
    graph_id: str,
    path: str = "",
    limit: int = 200,
) -> CallToolResult:
    """List files and directories under a path in a repository."""
    from codegraph.tools.get_repo_structure import get_repo_structure as _impl

    state = get_state(ctx)
    try:
        result = await _impl(
            state.adapter, GetRepoStructureArgs(graph_id=graph_id, path=path, limit=limit)
        )
    except Exception as ex:
        raise ToolError(
            f"Failed to get structure for '{graph_id}/{path}': {ex}. Check the repo is ingested."
        ) from ex
    lines = [
        f"Path '{result.path}' in '{graph_id}': {len(result.entries)} entries"
        + (" [truncated]" if result.truncated else "")
    ]
    for e in result.entries:
        if e.type == "dir":
            lines.append(f"  [dir]  {e.name}/")
        else:
            lines.append(f"  [file] {e.name}  ({e.language})")
    summary = "\n".join(lines)
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result.model_dump(),
    )


@mcp.tool()
async def find_file_dependencies(
    ctx: Context[ServerSession, AppState],
    graph_id: str,
    file_path: str,
    direction: str = "both",
    max_hops: int = 2,
) -> CallToolResult:
    """Find what files/functions depend on (or are depended on by) a given file.
    Use this to answer 'what breaks if I edit X?'. Returns imported_by, imports,
    callers, calls, and external symbols (stdlib/npm)."""
    from codegraph.tools.find_file_dependencies import find_file_dependencies as _impl

    state = get_state(ctx)
    try:
        result = await _impl(
            state.adapter,
            FindFileDependenciesArgs(
                graph_id=graph_id, file_path=file_path, direction=direction, max_hops=max_hops
            ),
        )
    except Exception as ex:
        raise ToolError(
            f"Failed to find dependencies for '{file_path}' in '{graph_id}': {ex}. "
            f"Verify Neo4j is running and the graph_id is ingested via list_repos. "
            f"Use get_repo_structure to confirm the file path exists."
        ) from ex
    lines = [f"Dependencies for '{file_path}' in '{graph_id}':"]
    if result.imported_by:
        lines.append(f"  Imported by ({len(result.imported_by)}):")
        for d in result.imported_by:
            lines.append(f"    - {d.path} ({d.kind}, via {d.via})")
    if result.imports:
        lines.append(f"  Imports ({len(result.imports)}):")
        for d in result.imports:
            lines.append(f"    - {d.path} ({d.kind}, via {d.via})")
    if result.callers:
        lines.append(f"  Called by ({len(result.callers)}):")
        for d in result.callers:
            lines.append(f"    - {d.path} ({d.kind}, via {d.via})")
    if result.calls:
        lines.append(f"  Calls ({len(result.calls)}):")
        for d in result.calls:
            lines.append(f"    - {d.path} ({d.kind}, via {d.via})")
    if result.external_symbols:
        lines.append(f"  External symbols ({len(result.external_symbols)}):")
        for s in result.external_symbols:
            lines.append(f"    - {s.name} ({s.kind})")
    if not any(
        [result.imported_by, result.imports, result.callers, result.calls, result.external_symbols]
    ):
        lines.append("  No dependencies found.")
    summary = "\n".join(lines)
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result.model_dump(),
    )


@mcp.tool()
async def search_nodes(
    ctx: Context[ServerSession, AppState],
    graph_id: str,
    query: str,
    kind: str = "any",
    limit: int = 10,
) -> CallToolResult:
    """Search for functions or files by name. Use this before find_file_dependencies
    or get_node_detail to find the exact path or node id."""
    from codegraph.tools.search_nodes import search_nodes as _impl

    state = get_state(ctx)
    try:
        result = await _impl(
            state.adapter, SearchNodesArgs(graph_id=graph_id, query=query, kind=kind, limit=limit)
        )
    except Exception as ex:
        raise ToolError(
            f"Search failed for '{query}' in '{graph_id}': {ex}. "
            f"Verify Neo4j is running and the graph_id is ingested via list_repos."
        ) from ex
    lines = [f"Search '{query}' in '{graph_id}' ({kind}): {len(result.hits)} hit(s)"]
    for h in result.hits:
        lines.append(f"  - {h.name}  (kind: {h.kind}, path: {h.path})")
    summary = "\n".join(lines)
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result.model_dump(),
    )


@mcp.tool()
async def get_node_detail(
    ctx: Context[ServerSession, AppState],
    graph_id: str,
    node_id: str,
) -> CallToolResult:
    """Get detailed information about a single node (function/file) by its id.
    Returns name, kind, path, and line range. Use search_nodes to find the node id first."""
    from codegraph.tools.get_node_detail import get_node_detail as _impl

    state = get_state(ctx)
    try:
        result = await _impl(state.adapter, GetNodeDetailArgs(graph_id=graph_id, node_id=node_id))
    except ValueError as ex:
        raise ToolError(str(ex)) from ex
    except Exception as ex:
        raise ToolError(
            f"Failed to get node '{node_id}' in '{graph_id}': {ex}. "
            f"Verify Neo4j is running. Use search_nodes to find a valid node id first."
        ) from ex
    summary = f"Node '{result.name}' (kind: {result.kind})"
    if result.path:
        summary += f"  path: {result.path}"
    if result.start_line:
        summary += f"  lines: {result.start_line}-{result.end_line}"
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent=result.model_dump(),
    )


@mcp.resource("codegraph://repos")
async def repos_resource() -> dict[str, Any]:
    """List all ingested repositories — read this at session start to ground yourself."""
    from codegraph.resources import read_repos_resource

    state = _state()
    return await read_repos_resource(state.adapter)


@mcp.resource("codegraph://schema/{graph_id}")
async def schema_resource(graph_id: str) -> dict[str, Any]:
    """Schema for a specific repo — labels, edges, and repo info."""
    from codegraph.resources import read_schema_resource

    state = _state()
    return await read_schema_resource(state.adapter, graph_id)


def serve() -> int:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")
    return 0
