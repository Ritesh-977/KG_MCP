"""CLI dispatch — subcommand routing + ingest orchestration."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codegraph",
        description="Knowledge-Graph MCP Server for GitHub repos",
    )
    p.add_argument("--version", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    ing = sub.add_parser("ingest", help="Clone + parse + load a GitHub repo into Neo4j")
    ing.add_argument("url", help="GitHub repo URL")
    ing.add_argument("--branch", default=None, help="Branch to ingest (default: repo default)")
    ing.add_argument("--force", action="store_true", help="Re-clone even if cached")

    sub.add_parser("serve", help="Run the MCP server (stdio transport)")

    rst = sub.add_parser("reset", help="Hard-wipe one repo from Neo4j (destructive)")
    rst.add_argument("--graph-id", required=True)

    sub.add_parser("ls", help="List ingested repos in Neo4j")
    return p


def _cmd_serve() -> int:
    from codegraph.server import serve
    return serve()


def _cmd_ls() -> int:
    import asyncio

    from codegraph.config import Settings
    from codegraph.repo.neo4j_adapter import Neo4jAdapter

    async def _go() -> int:
        s = Settings()
        ad = Neo4jAdapter.from_settings(s)
        try:
            await ad.connect()
            repos = await ad.list_repos()
            for r in repos:
                print(f"{r['graph_id']}\t{r.get('url', '')}")
        finally:
            with contextlib.suppress(Exception):
                await ad.close()
        return 0

    try:
        return asyncio.run(_go())
    except Exception as exc:
        print(f"ls failed: {exc}", file=sys.stderr)
        return 1


def _cmd_reset(args: argparse.Namespace) -> int:
    print("reset not yet implemented (Day 6)", file=sys.stderr)
    return 2


def _cmd_ingest(args: argparse.Namespace) -> int:
    try:
        asyncio.run(_ingest_async(args))
        return 0
    except Exception as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1


async def _ingest_async(args: argparse.Namespace) -> None:
    from codegraph.config import Settings
    from codegraph.ingestion.commits import collect_commits
    from codegraph.ingestion.git import clone_or_fetch, local_path_for, repo_slug_from_url
    from codegraph.ingestion.graph_builder import build_ingest_plan, run_plan
    from codegraph.ingestion.jsts_parser import parse_jsts
    from codegraph.ingestion.python_parser import parse_python
    from codegraph.ingestion.walker import walk_repo
    from codegraph.models.ingestion import ExtractedFile
    from codegraph.repo.neo4j_adapter import Neo4jAdapter

    settings = Settings()
    adapter = Neo4jAdapter.from_settings(settings)
    try:
        await adapter.connect()
        await adapter.apply_migrations()

        slug = repo_slug_from_url(args.url)
        dest = local_path_for(args.url, settings.repos_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        branch = clone_or_fetch(args.url, dest, args.branch, settings.ingest_depth)

        entries = walk_repo(dest)
        files: list[ExtractedFile] = []
        for fe in entries:
            source = fe.abspath.read_bytes()
            try:
                if fe.language == "py":
                    files.append(parse_python(fe.path, source))
                elif fe.language in ("js", "ts", "tsx"):
                    files.append(parse_jsts(fe.path, source, fe.language))
            except Exception as parse_exc:
                # Don't let one malformed file kill the whole ingest run
                print(f"WARNING: skipping {fe.path}: {parse_exc}", file=sys.stderr)

        commits = collect_commits(dest)
        known_paths = {ef.path for ef in files}
        plan = build_ingest_plan(
            slug=slug,
            url=args.url,
            branch=branch,
            files=files,
            commits=commits,
            known_paths=known_paths,
        )
        summary = await run_plan(adapter, plan)
        print(json.dumps({
            "graph_id": slug,
            "files": summary.files,
            "functions": summary.functions,
            "imports": summary.imports,
            "calls": summary.calls,
            "external_symbols": summary.external_symbols,
            "pruned": summary.pruned,
        }))
    finally:
        await adapter.close()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.version:
        print("codegraph 0.1.0")
        return 0
    if args.cmd is None:
        print("codegraph — run `codegraph --help` for usage", file=sys.stderr)
        return 0
    if args.cmd == "ingest":
        return _cmd_ingest(args)
    if args.cmd == "serve":
        return _cmd_serve()
    if args.cmd == "reset":
        return _cmd_reset(args)
    if args.cmd == "ls":
        return _cmd_ls()
    return 0
