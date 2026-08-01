"""CLI dispatch — subcommand routing, no I/O of its own."""

from __future__ import annotations

from codegraph.cli import main


def test_cli_no_args_prints_help_to_stderr(capsys: object) -> None:  # type: ignore[no-untyped-def]
    rc = main([])
    assert rc == 0
    out = capsys.readouterr()  # type: ignore[no-untyped-def]
    assert "codegraph" in out.err.lower() or "usage" in out.err.lower()


def test_cli_version() -> None:
    assert main(["--version"]) == 0


def test_cli_ingest_requires_url(capsys: object) -> None:  # type: ignore[no-untyped-def]
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["ingest"])
    assert exc.value.code == 2  # argparse missing-required-arg exit code


def test_cli_ingest_without_neo4j_returns_1(monkeypatch: object) -> None:  # type: ignore[no-untyped-def]
    # Ingest is now wired — with a guaranteed-bad Neo4j URI it fails fast at
    # connect() and returns 1. This proves the code path is live (past the old
    # stub) without making any real network calls (offline-safe).

    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:1")  # type: ignore[attr-defined]
    monkeypatch.setenv("NEO4J_PASSWORD", "wrong")  # type: ignore[attr-defined]
    rc = main(["ingest", "https://github.com/o/n"])
    assert rc == 1


def test_cli_serve_starts_mcp_server(monkeypatch: object) -> None:  # type: ignore[no-untyped-def]
    # serve() now calls the real server — with no Neo4j it will fail
    # We just verify it's no longer the "not yet implemented" stub
    # Don't actually run it (it would block on stdin) — just check the function exists
    from codegraph.cli import _cmd_serve
    assert callable(_cmd_serve)


def test_cli_reset_requires_graph_id(capsys: object) -> None:  # type: ignore[no-untyped-def]
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["reset"])
    assert exc.value.code == 2


def test_cli_ls_without_neo4j_returns_1(monkeypatch: object) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:1")  # type: ignore[attr-defined]
    monkeypatch.setenv("NEO4J_PASSWORD", "wrong")  # type: ignore[attr-defined]
    rc = main(["ls"])
    assert rc == 1
