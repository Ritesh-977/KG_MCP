# CodeGraph MCP

A Knowledge Graph MCP Server that analyzes GitHub repositories and stores their code structure in **Neo4j**.

It helps AI assistants understand relationships in a codebase, such as:

* Which files import a particular file?
* Which functions call another function?
* What could be affected if a function or file is changed?
* How are different parts of the repository connected?

Instead of searching through text, it uses a **graph of the codebase** to answer these questions.

## How It Works

CodeGraph has two main parts:

### 1. Ingest

```bash
codegraph ingest <git-url>
```

The ingestion process:

1. Clones the repository.
2. Reads the source files.
3. Parses Python using Python AST and JavaScript/TypeScript using Tree-sitter.
4. Creates nodes and relationships in Neo4j.
5. Stores files, functions, symbols, imports, and calls as a graph.

Example:

```text
Repository
   └── File
        ├── Function
        ├── Function
        └── Symbol

File ──IMPORTS──> File
Function ──CALLS──> Function
File ──DEFINES──> Function
```

### 2. Serve

```bash
codegraph serve
```

Runs the MCP server and exposes the graph to MCP-compatible clients such as Claude Desktop, Cursor, and other MCP hosts.

The server is **read-only** and only queries the existing Neo4j graph.

## Requirements

* Python 3.11+
* [uv](https://docs.astral.sh/uv/)
* Docker
* Neo4j 5.x

## Quick Start

```bash
# Install dependencies
make dev

# Start Neo4j
make up

# Ingest a repository
codegraph ingest https://github.com/owner/repo --branch main

# Check ingested repositories
codegraph ls

# Start the MCP server
codegraph serve
```

For development/testing, you can also run:

```bash
make inspector
```

to open the MCP Inspector.

## Connect to an MCP Client

Add CodeGraph to your MCP client configuration:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "uv",
      "args": ["run", "codegraph", "serve"]
    }
  }
}
```

## Available MCP Tools

| Tool                     | Description                                           |
| ------------------------ | ----------------------------------------------------- |
| `list_repos`             | List all ingested repositories                        |
| `init_repository_node`   | Check a repository and get basic statistics           |
| `get_repo_structure`     | Explore files and directories                         |
| `find_file_dependencies` | Find imports, imported-by files, callers, and callees |
| `search_nodes`           | Search for files, functions, and symbols              |
| `get_node_detail`        | Get details about a specific node                     |

### Resources

| Resource                        | Description                             |
| ------------------------------- | --------------------------------------- |
| `codegraph://repos`             | List of ingested repositories           |
| `codegraph://schema/{graph_id}` | Graph schema and repository information |

## CLI Commands

```bash
codegraph ingest <url>                # Ingest a repository
codegraph ingest <url> --branch X     # Ingest a specific branch
codegraph ingest <url> --force        # Re-clone and ingest
codegraph ls                          # List ingested repositories
codegraph serve                       # Start the MCP server
codegraph reset --graph-id OWNER/NAME # Delete a repository graph
```

## Configuration

Configuration is loaded from environment variables or `.env`.

| Variable            | Default                 | Description            |
| ------------------- | ----------------------- | ---------------------- |
| `NEO4J_URI`         | `bolt://localhost:7687` | Neo4j connection       |
| `NEO4J_USER`        | `neo4j`                 | Neo4j username         |
| `NEO4J_PASSWORD`    | `changeme123`           | Neo4j password         |
| `NEO4J_DB`          | `neo4j`                 | Neo4j database         |
| `REPOS_DIR`         | `./repos`               | Local repository cache |
| `INGEST_BATCH_SIZE` | `200`                   | Neo4j write batch size |
| `INGEST_DEPTH`      | `1`                     | Git clone depth        |
| `LOG_LEVEL`         | `INFO`                  | Logging level          |

## Project Structure

```text
src/codegraph/
├── cli.py          # CLI commands
├── server.py       # MCP server
├── config.py       # Configuration
├── ingestion/      # Repository parsing and graph creation
├── models/         # Data models
├── tools/          # MCP tools
└── repo/           # Neo4j integration

tests/              # Tests
```

## Development

```bash
make dev              # Install dependencies
make lint             # Run Ruff
make typecheck        # Run MyPy
make test             # Run tests
make test-slow        # Run all tests including integration tests
make inspector        # Start MCP Inspector
make snapshot-update  # Update tool-schema snapshots
```

## Status

**v0.1 — In Development**

Currently supports:

* Neo4j 5.x
* MCP over stdio
* Python parsing
* JavaScript/TypeScript parsing
* Repository dependency analysis

Cross-repository dependency analysis is planned for a future version.
