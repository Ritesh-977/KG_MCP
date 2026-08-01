"""MCP resources — read-only JSON the LLM reads at session start."""

from __future__ import annotations

from typing import Any

from codegraph.repo.port import CodeGraphRepository


async def read_repos_resource(repo: CodeGraphRepository) -> dict[str, Any]:
    """codegraph://repos — list all ingested repos (same data as list_repos tool)."""
    return {"repos": await repo.list_repos()}


async def read_schema_resource(repo: CodeGraphRepository, graph_id: str) -> dict[str, Any]:
    """codegraph://schema/{graph_id} — label/edge breakdown for one repo."""
    info = await repo.get_repo_info(graph_id=graph_id)
    if info is None:
        return {"error": f"graph '{graph_id}' not found. Call list_repos for available graphs."}
    return {
        "graph_id": graph_id,
        "labels": ["Repository", "File", "Function", "Symbol"],
        "edges": ["CONTAINS", "DEFINES", "IMPORTS", "CALLS"],
        "repo": info,
    }
