"""Migrations produce idempotent Cypher DDL — no DB needed."""

from __future__ import annotations

from codegraph.repo.migrations import build_migration_cypher


def test_migrations_returns_six_statements() -> None:
    stmts = build_migration_cypher()
    assert len(stmts) == 6
    for s in stmts:
        assert s.startswith("CREATE CONSTRAINT") or s.startswith("CREATE INDEX"), (
            f"unexpected statement prefix: {s}"
        )


def test_migrations_include_constraint_on_repository() -> None:
    stmts = build_migration_cypher()
    assert any("Repository" in s and "graph_id" in s for s in stmts)


def test_migrations_include_constraint_on_file() -> None:
    stmts = build_migration_cypher()
    assert any("File" in s and "graph_id" in s and "path" in s for s in stmts)


def test_migrations_include_constraint_on_function() -> None:
    stmts = build_migration_cypher()
    assert any("Function" in s and "qualified_name" in s for s in stmts)


def test_migrations_include_index_on_function_name() -> None:
    stmts = build_migration_cypher()
    # match "ON (fn.name)" precisely, not via substring of "qualified_name"
    assert any("Function" in s and "ON (fn.name)" in s for s in stmts)


def test_migrations_include_index_on_file_language() -> None:
    stmts = build_migration_cypher()
    assert any("File" in s and "ON (f.language)" in s for s in stmts)


def test_migrations_include_index_on_symbol() -> None:
    stmts = build_migration_cypher()
    assert any("Symbol" in s and "ON (s.graph_id, s.name)" in s for s in stmts)


def test_migrations_are_idempotent_markers() -> None:
    stmts = build_migration_cypher()
    for s in stmts:
        assert "IF NOT EXISTS" in s, f"missing IF NOT EXISTS: {s}"
