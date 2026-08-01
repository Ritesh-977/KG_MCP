"""Repository port (Protocol) — the storage abstraction tools talk to.

The CLI ingestion path writes through a concrete adapter that also implements
this surface; the MCP server reads through it. Every method is async.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class GraphError(Exception):
    """Raised on unrecoverable graph database errors."""


@runtime_checkable
class CodeGraphRepository(Protocol):
    """Read-mostly storage port. Writes happen via the ingestion adapter; the
    MCP server consumes the read methods. Every Cypher the adapter runs is
    parameterized and filters on `graph_id`.
    """

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def apply_migrations(self) -> None: ...

    async def list_repos(self) -> list[dict[str, Any]]: ...

    async def get_repo_info(self, *, graph_id: str) -> dict[str, Any] | None: ...

    async def get_repo_structure(
        self, *, graph_id: str, path: str, limit: int
    ) -> dict[str, Any]: ...

    async def find_file_dependencies(
        self, *, graph_id: str, file_path: str, direction: str, max_hops: int
    ) -> dict[str, Any]: ...

    async def search_nodes(
        self, *, graph_id: str, query: str, kind: str, limit: int
    ) -> list[dict[str, Any]]: ...

    async def get_node_detail(
        self, *, graph_id: str, node_id: str
    ) -> dict[str, Any] | None: ...
