# codegraph-mcp

Knowledge-Graph MCP Server for GitHub repos. Ingests any GitHub repo's code into a
Neo4j graph (Repository / File / Function nodes; CONTAINS / DEFINES / IMPORTS / CALLS
edges) and exposes that graph as read-only MCP tools to any MCP host
(Claude Desktop, opencode, Cursor, ...).

## Status

v0.1 — in development. stdio transport, Neo4j backend, Python + JS/TS parsing.

## Quick start

```bash
make dev                 # install dev deps (uv sync --extra dev)
make up                  # start local Neo4j via docker compose
cp .env.example .env     # adjust password if needed
make test                # unit + non-Docker tests
```

See `AGENTS.md` for the full command list and conventions.
