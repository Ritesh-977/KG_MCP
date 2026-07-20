# Contributing to Knowledge Graph MCP Server (`kg-mcp`)

This document orients a brand-new contributor to the `kg-mcp` project. It is the single source of truth for the project's scope, architecture, decisions, and conventions. Read it top-to-bottom before opening a PR.

---

## 1. Project Overview

`kg-mcp` is a **Model Context Protocol (MCP) server** that acts as a *persistent memory + reasoning layer* for AI agents — Claude Desktop, Cursor, and any custom MCP client. It lets LLMs store, read, and traverse entities and relationships via standard JSON-RPC tool calls instead of relying on an ephemeral context window.

**Why it exists.** LLMs today lose state between turns and between sessions. They re-derive facts, contradict themselves, and have no durable notion of *what is connected to what*. `kg-mcp` gives an agent a durable, traversable knowledge graph it can write to and query — but constrains those writes through a controlled vocabulary so the graph doesn't drift into chaos over time.

> The server exposes a graph database to LLMs as a small, strict set of MCP tools.

That sentence is the whole product. Everything else in this doc is implementation detail in service of it.

---

## 2. Tech Stack (decided)

These are locked choices — not proposals. Build against them, do not relitigate them.

| Layer | Decision |
|---|---|
| **Language / SDK** | Python 3.11+ with the official `mcp` SDK. Pin `mcp>=1.27,<2` until v2 goes stable on **2026-07-27**, then move to `mcp>=2.0`. Type-hinted functions auto-derive the `inputSchema` and `outputSchema` the LLM sees — **no hand-written JSON Schemas anywhere in the codebase.** |
| **Protocol** | MCP spec **`2026-07-28`**. JSON-RPC 2.0 primitives: `tools/list`, `tools/call`, `resources/read`, plus the `notifications/tools/list_changed` notification. |
| **Storage** | **Neo4j Community 5.x, external.** Server connects via `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` env vars. The server performs **no process management** — it never starts or stops Neo4j. Project root ships a `docker-compose.yml` for local dev (`docker compose up -d`). Queries are Cypher-native. **Every Cypher statement enforces `WHERE n.graph_id = $graph_id`** for namespace isolation the LLM cannot bypass. |
| **Schema migrations** | Idempotent Cypher DDL run at boot — `CREATE CONSTRAINT IF NOT EXISTS` on `(graph_id, name)`, property indexes on `entityType`, a vector index for `embedding`. No external migration runner. |
| **Embeddings** | Pluggable `VectorPort` abstraction. Default `EMBED_PROVIDER=local` → `sentence-transformers`, **lazy-loaded**, model selected by `EMBED_MODEL` env var (default **`all-MiniLM-L6-v2`** — 22MB, 384-dim, chosen for sub-second cold-start on stdio). Optional `EMBED_PROVIDER=openai` → `text-embedding-3-large`, gated by `OPENAI_API_KEY`. |
| **Transport** | **stdio only for v1** (`MCPServer.run(transport="stdio")`). Streamable-HTTP multi-tenant deployment is explicitly a **v1.1+ concern** and is **not in scope** for contributors right now. |
| **Config / libraries** | `pydantic` v2 for models + validation, `pydantic-settings` for config, the `neo4j` Python **async** driver, `pytest` + `pytest-asyncio` (asyncio mode `auto`) + `testcontainers-python` for the Neo4j testcontainer, `ruff` for lint, `mypy` for types, **`uv` as the package manager.** |

---

## 3. Architecture & Core Ontology

### Two-layer design

1. **MCP data layer** — JSON-RPC tools, resources, prompts exposed to the LLM.
2. **Storage layer** — Neo4j graph. Saved behind a **`GraphRepository` port** so a future Kuzu or Postgres+AGE adapter is a drop-in replacement. Tools never talk to Neo4j directly; they go through the port.

### Node schema (label `Entity`)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key. |
| `name` | STRING | **Lowercase-canonicalized** — the primary identity. |
| `name_variants` | STRING[] | Aliases the resolver fused into this node. |
| `entity_type` | STRING | Controlled vocabulary (see below). |
| `graph_id` | STRING | Isolation key — every query filters on this. |
| `observations` | STRING[] | **Append-only with dedup.** The LLM never overwrites; it only adds discrete facts. |
| `embedding` | FLOAT[384] | From `VectorPort`. |
| `confidence` | FLOAT 0..1 | |
| `provenance` | STRING | Where the fact came from. |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |
| `deleted` | BOOLEAN | **Soft-delete tombstone flag.** Traverse/search never return tombstoned nodes. |

### Relation schema (relationship type `Relation`)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key. |
| `source_id` | UUID | FK → `Entity.id`. |
| `target_id` | UUID | FK → `Entity.id`. |
| `relation_type` | STRING | Controlled vocabulary. |
| `graph_id` | STRING | **MUST equal both endpoints' `graph_id`** — cross-graph relations are rejected. |
| `properties` | JSON | Free-form, but small. |
| `created_at` | timestamp | |

### Controlled vocabulary (defaults)

Loaded from `vocab.yaml` at startup.

- **entity_types**: `project, person, organization, technology, concept, document, event, decision, system, dataset, policy`
- **relation_types**: `depends_on, owns, authored, uses, integrates_with, located_in, member_of, derived_from, contradicts, supports, scheduled_at, related_to, develops` (`develops` added for the Anthropic→Claude example)

**Hard-reject mode.** Writes outside the vocab are rejected, and the **allowed list is returned in the error message** so the LLM can self-correct on retry.

### Context isolation

Every Node and Relation carries a `graph_id` (e.g. `proj:acme-crm`, `domain:biomed`). All queries filter by `graph_id` **server-side**. The LLM passes `graph_id` as a parameter but can **never read across graphs** — it only sees results from the graph it named, and only graphs it has access to per `list_graphs`. The `graph_id` regex is enforced as **`^[\w:-]+$`**.

### Name resolver

Canonicalize with `strip().lower()`. Fuse variants by **name match + embedding cosine ≥ 0.92 + Levenshtein ≤ 2**. Example: `"PyTorch"` / `"pytorch "` / `"PyTorch Library"` all collapse to one node. **Never accept the LLM's casing as identity.**

---

## 4. The Tools

The LLM sees 7 tools. Their `inputSchema` and `outputSchema` auto-generate from pydantic type hints — there are no hand-written schemas to maintain.

| # | Tool | One-line purpose |
|---|---|---|
| 1 | `add_entities` | Upsert nodes by name within a `graph_id`; observations appended + deduped; `entity_type` validated against vocab; on persist failure returns `isError:true` with `partial` counts of what already succeeded. |
| 2 | `add_relations` | Connect existing nodes. **Strict two-phase:** missing endpoints are rejected with actionable guidance ("target 'X' not found in graph 'Y'; call `add_entities` first"). No auto-create flag, no opt-in. |
| 3 | `search_nodes` | `keyword` \| `semantic` \| `hybrid` entry point; returns **entity summaries only** (never neighbors). Hybrid = union + rank fusion. |
| 4 | `query_graph` | Bounded multi-hop traversal, `hops` 0–4, `relationFilter`, `maxNodes` cap (default 50); when truncated returns `truncated:true` + `hint` so the LLM narrows seeds. |
| 5 | `list_graphs` | What graphs the caller may access. |
| 6 | `delete_entities` | **Soft-delete only** — sets the tombstone flag; traverse/search never return tombstoned nodes. |
| 7 | `register_schema` | Admin-only; extends vocab at runtime; emits `notifications/tools/list_changed` so connected clients refresh tool listing without reconnect. |

### MCP Resources (read-only JSON the LLM reads at session start)

- `kg://vocab/latest`
- `kg://graphs`
- `kg://schema/{graph_id}`

These ground the LLM's choice of types before it ever calls a tool.

---

## 5. Error Model

Two tiers, matching the MCP spec exactly.

### Tier 1 — Malformed arguments

→ JSON-RPC **protocol error `-32602`**, surfaced via the SDK's pydantic integration. The server does not hand-roll this.

### Tier 2 — Business / DB failure

(e.g. unknown vocab type, missing target node, DB exception) → tool result with **`isError:true`** and a **plain-text actionable message**, plus `partial` counts when some entities succeeded but a later one failed. The LLM can read this text and self-correct on retry.

### Unknown resource URI

→ JSON-RPC **`-32` / `NOT_FOUND`**.

### Key principle

Errors are designed to be **LLM-readable**. They must tell the model what to do next, not surface a stack trace:

```
Fix and retry — entities[0].entityType: value 'company' not in vocab. Allowed: [project, person, organization, technology, concept, document, event, decision, system, dataset, policy]
```

---

## 6. Project Structure

```
kg-mcp/
├─ pyproject.toml                    # uv/pip metadata, deps, ruff/mypy/pytest config
├─ README.md                         # install + Claude Desktop/Cursor config snippets
├─ CONTRIBUTING.md                   # THIS document
├─ AGENTS.md                          # opencode agent instructions (lint/test cmds)
├─ docker-compose.yml                 # one-click Neo4j for local dev
├─ .env.example                        # NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBED_PROVIDER, EMBED_MODEL, OPENAI_API_KEY
├─ .gitignore
├─ vocab.yaml                          # controlled vocab (entity_types, relation_types)
├─ Makefile                            # dev shortcuts: test, lint, typecheck, inspector
│
├─ src/kgmcp/
│  ├─ __init__.py
│  ├─ __main__.py                      # `python -m kgmcp` → calls server.main(); also hosts `reset` CLI subcommand (hard-wipe one graph_id, NOT exposed as a tool)
│  ├─ server.py                        # MCPServer instance + @mcp.tool() registrations + main()
│  ├─ config.py                        # Settings via pydantic-settings (env + pyproject)
│  ├─ logging_setup.py                # stderr-only logging (stdio transport rule)
│  ├─ vocab.py                         # Vocab loader + EntityTypeError + RelationTypeError
│  ├─ errors.py                        # ValidationError → TextContent isError handler
│  ├─ resources.py                     # kg://vocab/{ver}, kg://graphs, kg://schema/{graph_id}
│  │
│  ├─ models/
│  │  ├─ __init__.py
│  │  ├─ entities.py                   # EntityIn, EntityOut, AddEntitiesArgs, AddEntitiesResult
│  │  ├─ relations.py                  # RelationIn, RelationOut, AddRelationsArgs, Result
│  │  ├─ search.py                     # SearchArgs, SearchResult
│  │  ├─ traversal.py                  # QueryGraphArgs, SubgraphResult
│  │  └─ common.py                     # GraphId, Confidence, Provenance, Error payload
│  │
│  ├─ repo/                            # storage port — every write goes through here
│  │  ├─ __init__.py
│  │  ├─ port.py                       # GraphRepository Protocol/ABC
│  │  ├─ neo4j_adapter.py              # neo4j async driver, Cypher
│  │  ├─ resolver.py                   # name canonicalizer + name-variant fusion
│  │  └─ migrations.py                 # Cypher DDL: constraints, indexes (idempotent)
│  │
│  ├─ vectors/                         # VectorPort — pluggable embeddings
│  │  ├─ __init__.py
│  │  ├─ port.py                       # VectorPort Protocol
│  │  ├─ local.py                      # sentence-transformers adapter (lazy-loaded, default)
│  │  └─ openai.py                     # hosted embeddings adapter (env-gated)
│  │
│  └─ tools/                           # one module per @mcp.tool — thin, validates + delegates
│     ├─ __init__.py
│     ├─ add_entities.py
│     ├─ add_relations.py
│     ├─ search_nodes.py
│     ├─ query_graph.py
│     ├─ list_graphs.py
│     ├─ delete_entities.py
│     └─ register_schema.py
│
└─ tests/
   ├─ conftest.py                       # fixtures: in-memory Client(mcp), testcontainer Neo4j, vocab, VectorPort stub
   ├─ unit/
   │  ├─ test_models_validation.py
   │  ├─ test_vocab.py
   │  ├─ test_resolver.py
   │  └─ test_errors.py
   ├─ integration/
   │  ├─ test_neo4j_adapter.py
   │  ├─ test_add_entities_tool.py
   │  ├─ test_add_relations_tool.py
   │  ├─ test_search_nodes_tool.py
   │  ├─ test_query_graph_tool.py
   │  └─ test_resources.py
   ├─ contract/
   │  └─ test_tool_schemas.py          # golden: tools/list output matches documented schemas
   └─ e2e/
      └─ test_inspector_smoke.py       # `uv run mcp dev` round-trip
```

**Top-level directory responsibilities:**

| Path | Responsibility |
|---|---|
| `src/kgmcp/` | All server source. Subdivided into `models/` (pydantic DTOs), `repo/` (storage port + Neo4j adapter + resolver + migrations), `vectors/` (embedding port + adapters), `tools/` (one thin module per `@mcp.tool`). |
| `tests/` | Four layers: `unit/` (pure logic), `integration/` (Neo4j-backed via testcontainer), `contract/` (golden `tools/list` snapshots), `e2e/` (Inspector smoke). |

---

## 7. Implementation Roadmap

Each step requires the prior step's tests green before being started. This is what makes the order **rigorous**, not just convenient — do not skip ahead.

| Step | Inputs available from prior steps | Output & done-when |
|---|---|---|
| **0. Project scaffold** | — | `uv init`, pin deps, `Makefile`, `AGENTS.md`. **Done when** `uv run mcp dev src/kgmcp/server.py` boots Inspector with zero tools and `uv run pytest` collects 0 tests with exit 0. |
| **1. Vocab module** | Step 0 scaffold | Load YAML, raise `EntityTypeError` / `RelationTypeError` with allowed list. **Done when** unknown-type unit tests pass. |
| **2. Domain models** | Step 1 vocab | Pydantic strict validators, name canonicalization, `GraphId` regex `^[\w:-]+$`. **Done when** `test_models_validation.py` green for all field paths. |
| **3. Neo4j repo** | Step 2 models | `GraphRepository` port, async adapter, migrations, name resolver. **Done when** adapter unit tests pass against testcontainer Neo4j. |
| **4. VectorPort** | Step 2 models | Port + local (lazy + configurable model) + openai adapters, env-driven factory. **Done when** Protocol-conformance tests pass for both adapters with mocked backends. |
| **5. Error handler** | Steps 1–2 | Pydantic `ValidationError` → list of `TextContent` with field + allowed enum. **Done when** `test_errors.py` golden strings asserted. |
| **6. Tool `add_entities`** | Steps 3, 4, 5 | Pydantic validate → `repo.upsert_node` → on `GraphError` return `isError` payload with `partial` counts. **Done when** insert + re-insert + rejection integration tests green. |
| **7. Tool `add_relations`** | Step 6 | Reject missing endpoints with actionable guidance; cross-`graph_id` rejection. **Done when** missing-target test asserts the missing name is in the error message. |
| **8. Tool `search_nodes`** | Steps 3, 4 | `keyword` / `semantic` / `hybrid`. **Done when** all three modes green and hybrid recall@10 ≥ threshold on fixture. |
| **9. Tool `query_graph`** | Step 3 | Bounded hop depth, `relationFilter`, `maxNodes` cap with `truncated:true` hint. **Done when** a 4-hop graph requested with `hops=2` returns no hops=3 nodes and `truncated:true` when capped. |
| **10a. Admin tools + notifications** | Steps 1, 3 | `register_schema` fires `notifications/tools/list_changed`; `delete_entities` soft-tombstone; `list_graphs`. **Done when** a connected client sees new tool listing without reconnect. |
| **10b. Resources** | Steps 1, 3 | `kg://vocab/latest`, `kg://graphs`, `kg://schema/{graph_id}`. **Done when** `resources/read` returns valid JSON for all three URIs. |
| **11. Contract tests** | Steps 6–10b | Golden snapshots of `tools/list` JSON compared to documented schemas. **Done when** snapshot diff = exit 0. |
| **12. README + config snippets + docker-compose.yml** | Step 11 | Claude Desktop `mcpServers` block, Cursor config, `.env.example`. **Done when** end-to-end smoke fires `add_entities` via Inspector. |
| **13. CI** | Step 12 | `ruff check`, `mypy src`, `pytest -m "not slow"`, contract snapshot diff blocks merge. **Done when** CI green on a feature branch before tagging v1.0. |

---

## 8. Testing Strategy

### Layer breakdown

| Layer | Scope |
|---|---|
| **unit** | Pure logic in `models/`, `vocab.py`, `repo/resolver.py`, `errors.py`. No I/O. |
| **integration** | Neo4j-backed tools + adapter via `testcontainers-python` `neo4j:5.x`. |
| **contract** | Golden snapshots of `tools/list` schema. |
| **e2e** | Inspector smoke — `uv run mcp dev ...` round-trip. |

### Test isolation rules (established in `conftest.py`)

1. **Every Neo4j-backed test gets a FRESH logical `graph_id`** (`test-{uuid}`) — no shared state between tests.
2. **`VectorPort` is patched with a deterministic stub** returning a fixed vector per input string. Tests **never** actually load `sentence-transformers` (slow + ~400MB).
3. **Tests run offline by default.** The `EMBED_PROVIDER=openai` integration test is `@pytest.mark.slow` and is **skipped unless `OPENAI_API_KEY` is present**.
4. **`pytest-asyncio` mode `auto`** — no manual `@pytest.mark.asyncio` decorators.
5. **Contract tests live in `tests/contract/`** with their own snapshot directory. Updating snapshots is `make snapshot-update` — a reviewable action, never accidental.

### Coverage targets

| Module | Target |
|---|---|
| Pure-logic modules (`models/`, `vocab.py`, `errors.py`, `resolver.py`) | ≥ 95% |
| `repo/neo4j_adapter.py` | ≥ 80% |
| `tools/` | ≥ 85% |
| `vectors/` | ≥ 70% |

### CI gates (every push)

- `ruff check`
- `mypy src`
- `pytest -m "not slow"`
- Contract snapshot diff passes

---

## 9. Known Failure Pitfalls & Mitigations

### 1. Context-window bloat from traversal

`query_graph` returning a 4-hop subgraph easily yields hundreds of nodes.

**Mitigations:**
- Hard `maxNodes` default **50**.
- Server-side relevance ranking (fold in `confidence` + embedding distance).
- Return edges-first summary + node-detail-on-demand.
- Provide a `summarize_only` flag.

### 2. Naming / entity-identity chaos

`"PyTorch"`, `"pytorch"`, `"PyTorch Library"` become three separate nodes without intervention.

**Mitigations:**
- Server canonicalizes name to `strip().lower()`.
- `name_variants[]` + resolver fuses by **embedding cosine ≥ 0.92 + Levenshtein ≤ 2**.
- **Never accept the LLM's casing as identity.**

### 3. Schema drift / hallucinated relations

The LLM invents `relationType: "is_really_great_at"`.

**Mitigations:**
- `vocab` resource + **server-side rejection with the allowed enum in the error message** so the LLM self-corrects on retry.
- `relation_type` direction convention so `depends_on` isn't stored backwards.

---

## 10. Decision Log

These decisions are locked. Do not reverse them by accident — read the *why* before proposing a change.

| Decision | Why |
|---|---|
| **Python over TypeScript** | Type-hinted pydantic models become *both* the LLM's `inputSchema` *and* the server validation boundary — single source of truth. Python's AI/embedding ecosystem is the strongest. |
| **Neo4j over Kuzu / Postgres+AGE** | Cypher-native multi-hop traversal is the core workload. External Neo4j keeps the stdio server simple and matches how Plan/develop already used Neo4j in prior projects. |
| **stdio only for v1** | A single MCP client ↔ single server process has zero network overhead and zero auth surface. Multi-tenant streamable-HTTP is a v1.1 evolution behind OAuth. |
| **Hard-reject vocab** | Schema drift is the #1 cause of unusable knowledge graphs. Rejecting with the allowed-list-in-error makes the LLM self-correct. |
| **Soft-delete + CLI-only reset** | A mistaken LLM tool call can never destroy data. Only an operator running `python -m kgmcp reset --graph-id X` can hard-wipe a namespace. |
| **Strict two-phase relations (no auto-create targets)** | Predictable graphs. Reduces stub nodes that never get filled in. |

---

## 11. How to Contribute

### First-time setup

```bash
git clone <repo> kg-mcp
cd kg-mcp
uv sync
cp .env.example .env
docker compose up -d
uv run pytest -m "not slow"
```

The last command should be green. If it isn't, stop and fix the environment before doing anything else.

### Branching & PRs

- Branch from `main`. Name branches `feat/<thing>` or `fix/<thing>`.
- **One concern per PR.** Do not bundle unrelated changes.
- Before re-asking for review: run `make lint typecheck test` locally — must pass.
- Update contract snapshots **deliberately** via `make snapshot-update` if your tool schema change is intentional. Never do this silently.

### Hard rules

- **Every new tool must have** a unit test for validation **and** an integration test for the happy path + at least one error path (returning `isError:true`).
- **Every Cypher query MUST be parameterized and include a `graph_id` filter** — no exceptions, no string formatting.
- **All tool errors must be LLM-readable** — do not surface stack traces; surface "what to do next" text.
- **Don't add a new tool without** (a) a `vocab.yaml` entry if it's a new relation/entity type, (b) a contract snapshot update, (c) README surface.

---

## 12. Glossary

| Term | Definition |
|---|---|
| **MCP** | Model Context Protocol — the open standard that lets an LLM client discover and call tools, read resources, and use prompts exposed by a server. |
| **JSON-RPC** | JSON Remote Procedure Call 2.0 — the wire protocol MCP rides on top of. |
| **stdio transport** | MCP transport where the client spawns the server as a subprocess and communicates over the process's stdin/stdout. Zero network, zero auth. The only transport v1 supports. |
| **Streamable HTTP transport** | MCP transport where the server is a long-lived HTTP service. Supports multi-tenancy. A v1.1+ concern, behind OAuth. |
| **tool** | An MCP primitive the LLM can *call* (via `tools/call`) to perform an action with structured arguments and a structured result. |
| **resource** | An MCP primitive the LLM can *read* (via `resources/read`) — addressed by URI, returns bytes/JSON. Read-only. |
| **prompt** | The MCP kind: a reusable, parameterized prompt template the client can pull and render. |
| **`tools/list_changed` notification** | A server-pushed notification telling connected clients the tool listing has changed and they should re-fetch `tools/list` without reconnecting. |
| **Cypher** | Neo4j's declarative graph query language. All storage-layer queries in this project are Cypher. |
| **graph_id** | The string isolation key (e.g. `proj:acme-crm`) every node and relation carries. All queries filter on it server-side. Regex `^[\w:-]+$`. |
| **namespace isolation** | The guarantee that a query naming `graph_id=X` can only ever see nodes/relations whose `graph_id=X`. Enforced in Cypher, not in client trust. |
| **append-only observation** | An `Entity.observations[]` entry. The LLM adds discrete facts but never overwrites or deletes existing ones — dedup is server-side. |
| **name resolver** | The component that canonicalizes a name to `strip().lower()` and fuses variants (cosine ≥ 0.92 + Levenshtein ≤ 2) into a single node. |
| **soft-delete tombstone** | The `deleted` boolean on `Entity`. Set, never unset by tools. Traverse/search filter tombstoned nodes out. Hard-wipe is CLI-only (`python -m kgmcp reset`). |
| **VectorPort** | The pluggable abstraction over embedding providers. `local` → `sentence-transformers`; `openai` → hosted. Selected by `EMBED_PROVIDER`. |
| **hybrid search** | `search_nodes` mode that unions keyword and semantic results then fuses their ranks. |
| **pattern truncation** | When `query_graph` hits the `maxNodes` cap it stops and returns `truncated:true` plus a `hint` so the LLM narrows its seed set. |
| **contract snapshot** | A golden JSON file capturing the exact `tools/list` output. Drift blocks merge until deliberately updated via `make snapshot-update`. |
| **testcontainer** | A `testcontainers-python` Neo4j container spun up per test session/fixture to give integration tests a real, isolated Neo4j 5.x. |
