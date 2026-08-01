"""Neo4j-backed CodeGraphRepository. Sync driver wrapped with asyncio.to_thread.

Mirrors the proven pattern from the sibling kg-mcp: every Cypher statement is
parameterized and filters on graph_id. Relationship-type literals are
regex-validated before substitution (Neo4j cannot parameterize rel types).
Read methods beyond connect/migrations/list_repos/get_repo_info are stubs
implemented in Day 4/5 tasks.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from neo4j import Driver, GraphDatabase

from codegraph.config import Settings
from codegraph.repo.migrations import build_migration_cypher

_REL_TYPE_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class Neo4jAdapter:
    """Concrete CodeGraphRepository backed by a Neo4j 5.x driver."""

    def __init__(self, *, uri: str, user: str, password: str, db: str) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._db = db

    @classmethod
    def from_settings(cls, settings: Settings) -> Neo4jAdapter:
        return cls(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            db=settings.neo4j_db,
        )

    async def connect(self) -> None:
        await asyncio.to_thread(self._driver.verify_connectivity)

    async def close(self) -> None:
        await asyncio.to_thread(self._driver.close)

    async def apply_migrations(self) -> None:
        for stmt in build_migration_cypher():
            await self._run_write(stmt)

    # --- read methods (implemented now) ---

    async def list_repos(self) -> list[dict[str, Any]]:
        rows = await self._run_read(
            "MATCH (r:Repository) "
            "RETURN r.graph_id AS graph_id, r.name AS name, r.url AS url, "
            "       r.default_branch AS default_branch, r.ingested_at AS ingested_at"
        )
        return [_normalize_repo_row(r) for r in rows]

    async def get_repo_info(self, *, graph_id: str) -> dict[str, Any] | None:
        rows = await self._run_read(
            "MATCH (r:Repository {graph_id: $gid}) "
            "OPTIONAL MATCH (f:File {graph_id: $gid}) WHERE f.deleted = false "
            "OPTIONAL MATCH (fn:Function {graph_id: $gid}) "
            "RETURN r.graph_id AS graph_id, r.name AS name, r.url AS url, "
            "       r.default_branch AS default_branch, r.ingested_at AS ingested_at, "
            "       count(DISTINCT f) AS file_count, count(DISTINCT fn) AS function_count",
            gid=graph_id,
        )
        if not rows or rows[0].get("graph_id") is None:
            return None
        return _normalize_repo_row(rows[0])

    # --- read methods implemented in Day 4/5 ---

    async def get_repo_structure(
        self, *, graph_id: str, path: str, limit: int
    ) -> dict[str, Any]:
        prefix = (path + "/") if path else ""
        rows = await self._run_read(
            "MATCH (f:File {graph_id: $gid}) "
            "WHERE f.deleted = false AND ($prefix = '' OR f.path STARTS WITH $prefix) "
            "RETURN f.path AS p, f.language AS lang "
            "ORDER BY f.path LIMIT $lim",
            gid=graph_id, prefix=prefix, lim=limit + 1,
        )
        entries: list[dict[str, Any]] = []
        seen_dirs: set[str] = set()
        for r in rows:
            rel = r["p"][len(prefix):] if prefix else r["p"]
            parts = rel.split("/")
            if len(parts) == 1:
                entries.append({"name": parts[0], "type": "file", "language": r["lang"]})
            else:
                d = parts[0]
                if d not in seen_dirs:
                    seen_dirs.add(d)
                    entries.append({"name": d, "type": "dir"})
        truncated = len(rows) > limit
        return {"path": path, "entries": entries[:limit], "truncated": truncated}

    async def find_file_dependencies(
        self, *, graph_id: str, file_path: str, direction: str, max_hops: int
    ) -> dict[str, Any]:
        # imported_by: files that IMPORT this file
        imported_by = await self._run_read(
            "MATCH (src:File {graph_id: $gid})-[:IMPORTS]->(tgt:File {graph_id: $gid, path: $p}) "
            "WHERE src.deleted = false "
            "RETURN src.path AS path, 'file' AS kind, 'imported_by' AS via, 1 AS hop",
            gid=graph_id, p=file_path,
        ) if direction in ("imported_by", "both") else []

        # imports: files this file IMPORTS
        imports = await self._run_read(
            "MATCH (src:File {graph_id: $gid, path: $p})-[:IMPORTS]->(tgt:File {graph_id: $gid}) "
            "WHERE tgt.deleted = false "
            "RETURN tgt.path AS path, 'file' AS kind, 'imports' AS via, 1 AS hop",
            gid=graph_id, p=file_path,
        ) if direction in ("imports", "both") else []

        # callers: functions in OTHER files that CALL a function defined in this file
        # Traverse via DEFINES edge (language-agnostic) instead of qname prefix matching
        callers = await self._run_read(
            "MATCH (caller:Function {graph_id: $gid})-[:CALLS]->(callee:Function {graph_id: $gid}) "
            "<-[:DEFINES]-(calleeFile:File {graph_id: $gid, path: $p}) "
            "RETURN caller.qualified_name AS path, 'function' AS kind, 'called_by' AS via, 1 AS hop",
            gid=graph_id, p=file_path,
        ) if direction in ("imported_by", "both") else []

        # calls: functions this file's functions CALL
        # Traverse via DEFINES edge (language-agnostic)
        calls = await self._run_read(
            "MATCH (callerFile:File {graph_id: $gid, path: $p})-[:DEFINES]->"
            "(caller:Function {graph_id: $gid})-[:CALLS]->(callee:Function {graph_id: $gid}) "
            "RETURN callee.qualified_name AS path, 'function' AS kind, 'calls' AS via, 1 AS hop",
            gid=graph_id, p=file_path,
        ) if direction in ("imports", "both") else []

        # external symbols (unresolved imports from File + unresolved calls from Function)
        ext_imports = await self._run_read(
            "MATCH (f:File {graph_id: $gid, path: $p})-[:IMPORTS]->(s:Symbol {graph_id: $gid}) "
            "RETURN s.name AS name, s.kind AS kind",
            gid=graph_id, p=file_path,
        )
        ext_calls = await self._run_read(
            "MATCH (f:File {graph_id: $gid, path: $p})-[:DEFINES]->(fn:Function {graph_id: $gid})"
            "-[:CALLS]->(s:Symbol {graph_id: $gid}) "
            "RETURN s.name AS name, s.kind AS kind",
            gid=graph_id, p=file_path,
        )
        ext = ext_imports + ext_calls

        return {
            "file": {"path": file_path, "graph_id": graph_id},
            "imported_by": imported_by,
            "imports": imports,
            "callers": callers,
            "calls": calls,
            "external_symbols": ext,
            "truncated": False,
            "hint": None,
        }

    async def search_nodes(
        self, *, graph_id: str, query: str, kind: str, limit: int
    ) -> list[dict[str, Any]]:
        q = query.lower()
        if kind == "function":
            cypher = (
                "MATCH (fn:Function {graph_id: $gid}) WHERE toLower(fn.name) CONTAINS $q "
                "RETURN fn.qualified_name AS qualified_name, fn.name AS name, fn.kind AS kind, '' AS path, 1.0 AS score "
                "LIMIT $lim"
            )
        elif kind == "file":
            cypher = (
                "MATCH (f:File {graph_id: $gid}) WHERE f.deleted = false AND toLower(f.path) CONTAINS $q "
                "RETURN '' AS qualified_name, f.path AS name, 'file' AS kind, f.path AS path, 1.0 AS score "
                "LIMIT $lim"
            )
        else:
            cypher = (
                "MATCH (n {graph_id: $gid}) WHERE "
                "(n:Function AND toLower(n.name) CONTAINS $q) "
                "OR (n:File AND n.deleted = false AND toLower(n.path) CONTAINS $q) "
                "RETURN coalesce(n.qualified_name, '') AS qualified_name, "
                "coalesce(n.name, n.path) AS name, "
                "CASE WHEN n:Function THEN 'function' WHEN n:File THEN 'file' ELSE 'other' END AS kind, "
                "coalesce(n.path, '') AS path, 1.0 AS score LIMIT $lim"
            )
        return await self._run_read(cypher, gid=graph_id, q=q, lim=limit)

    async def get_node_detail(
        self, *, graph_id: str, node_id: str
    ) -> dict[str, Any] | None:
        rows = await self._run_read(
            "MATCH (n {graph_id: $gid}) WHERE elementId(n) = $nid "
            "RETURN elementId(n) AS id, coalesce(n.name, n.path) AS name, "
            "CASE WHEN n:Function THEN n.kind WHEN n:File THEN 'file' ELSE 'other' END AS kind, "
            "coalesce(n.path, '') AS path, n.start_line AS sl, n.end_line AS el",
            gid=graph_id, nid=node_id,
        )
        if not rows:
            return None
        return {
            "id": rows[0]["id"],
            "name": rows[0]["name"],
            "kind": rows[0]["kind"],
            "path": rows[0]["path"] or None,
            "start_line": rows[0].get("sl"),
            "end_line": rows[0].get("el"),
        }

    # --- low-level exec used by graph_builder + tests ---

    async def _run_read(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._exec_read, cypher, params)

    async def _run_write(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._exec_write, cypher, params)

    def _exec_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with self._driver.session(database=self._db) as session:
            return session.execute_read(lambda tx: tx.run(cypher, params).data())

    def _exec_write(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with self._driver.session(database=self._db) as session:
            return session.execute_write(lambda tx: tx.run(cypher, params).data())

    async def soft_cleanup(self, graph_id: str) -> None:
        """Test/dev helper: remove all nodes/rels for a graph_id namespace."""
        await self._run_write(
            "MATCH (n {graph_id: $gid}) DETACH DELETE n", gid=graph_id
        )


def _normalize_repo_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert Neo4j temporal types to JSON-safe strings."""
    out = dict(row)
    ts = out.get("ingested_at")
    if ts is not None and not isinstance(ts, str):
        # Neo4j returns datetime objects — convert to ISO string for pydantic
        to_native = getattr(ts, "to_native", None)
        if callable(to_native):
            out["ingested_at"] = to_native().isoformat()
        elif hasattr(ts, "isoformat"):
            out["ingested_at"] = ts.isoformat()
        else:
            out["ingested_at"] = str(ts)
    return out
