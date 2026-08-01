# AGENTS.md

## Project

`codegraph-mcp` — Knowledge-Graph MCP Server for GitHub repos. Python 3.11+,
`mcp>=1.27,<2` (FastMCP, stable v1.x), Neo4j 5.x backend, stdio transport,
Python `ast` + tree-sitter (JS/TS) parsing.

Two-process design: an offline `codegraph` CLI ingests repos into Neo4j; a
FastMCP stdio server exposes that graph as read-only tools to any MCP host
(Claude Desktop, opencode, Cursor, ...).

## Common commands

| Task | Command |
|---|---|
| Install dev deps | `make dev` (also `make install` for runtime only) |
| Start Neo4j locally | `make up` (needs Docker) |
| Stop Neo4j | `make down` |
| Run unit tests | `make test` |
| Run all tests (incl. Docker) | `make test-slow` |
| Lint | `make lint` |
| Type check | `make typecheck` |
| Boot MCP Inspector | `make inspector` |
| Run server (stdio) | `make run` |

## Before requesting a review

Run `make lint typecheck test` locally — all must pass. If you intentionally
changed a tool's input/output schema, regenerate contract snapshots with
`make snapshot-update` and review the diff before opening the PR.

## Conventions

- **Every Cypher query MUST be parameterized and contain a `WHERE n.graph_id = $graph_id`
  (or equivalent) predicate.** Never string-format values into Cypher.
- **stdio transport rule:** the server MUST NOT write anything to `stdout`
  except valid MCP messages. All logging goes to `stderr`. `stdout` is a
  JSON-RPC channel — a stray `print()` corrupts the protocol stream.
- **No write tools exposed to the LLM.** The MCP server is read-only;
  ingestion runs offline as a CLI command.
- **Tool errors are LLM-readable:** surface "what to do next" text, never
  stack traces. Two tiers: malformed args → JSON-RPC `-32602` (SDK-handled
  via pydantic); business/DB errors → `isError:true` with plain-text guidance.
- **Every new tool needs:** a pydantic input model in `src/codegraph/models/`,
  a thin module in `src/codegraph/tools/`, a unit test for validation, and an
  integration test for happy + at least one `isError:true` path.
- **Do not add a new node label / edge type** without an entry in the design
  spec and a contract snapshot update.
- **Never expose a hard-delete tool to the LLM.** Destructive wipes only via
  the `python -m codegraph reset --graph-id X` CLI subcommand.
- **Soft-delete tombstones** for pruned files (`deleted=true`); hard-wipe is
  CLI-only via `codegraph reset --graph-id X`.
- **Repo slug = `graph_id`** (e.g. `owner/name`); enforced in every Cypher
  statement for multi-repo isolation.
- **File paths are repo-relative POSIX** (forward slashes) regardless of OS.
- **Tests run offline** — no real GitHub clones; tests use `tests/fixtures/`
  repos. Neo4j-backed tests use `testcontainers-python` with a fresh
  `graph_id` per test.
- **`pytest-asyncio` mode `auto`** — no manual `@pytest.mark.asyncio`.