"""Idempotent Cypher DDL — constraints + indexes, run at server boot.

Every statement uses `IF NOT EXISTS` so `apply_migrations()` is safe to call
on every boot. Schema matches the design spec §5 (Repository/File/Function/
Symbol labels, (graph_id, path) / (graph_id, qualified_name) uniqueness).
"""

from __future__ import annotations


def build_migration_cypher() -> list[str]:
    """Return the ordered list of idempotent DDL statements."""
    return [
        "CREATE CONSTRAINT repository_graph_id IF NOT EXISTS "
        "FOR (r:Repository) REQUIRE r.graph_id IS UNIQUE",
        "CREATE CONSTRAINT file_graph_id_path IF NOT EXISTS "
        "FOR (f:File) REQUIRE (f.graph_id, f.path) IS UNIQUE",
        "CREATE CONSTRAINT function_graph_id_qname IF NOT EXISTS "
        "FOR (fn:Function) REQUIRE (fn.graph_id, fn.qualified_name) IS UNIQUE",
        "CREATE INDEX file_language IF NOT EXISTS FOR (f:File) ON (f.language)",
        "CREATE INDEX function_name IF NOT EXISTS FOR (fn:Function) ON (fn.name)",
        "CREATE INDEX symbol_graph_id_name IF NOT EXISTS "
        "FOR (s:Symbol) ON (s.graph_id, s.name)",
    ]
