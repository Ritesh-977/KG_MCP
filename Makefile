.PHONY: dev install up down test test-slow lint typecheck inspector run serve snapshot-update

dev:            ## install dev deps
	uv sync --extra dev

install:        ## install runtime deps only
	uv sync

up:             ## start local Neo4j
	docker compose up -d neo4j

down:           ## stop Neo4j
	docker compose down

test:           ## unit + non-Docker tests
	uv run pytest -m "not slow and not integration"

test-slow:      ## all tests incl. Docker integration
	uv run pytest

lint:           ## ruff
	uv run ruff check src tests

typecheck:      ## mypy
	uv run mypy src

inspector:      ## MCP Inspector
	uv run mcp dev src/codegraph/server.py

run:            ## run server (stdio)
	uv run codegraph serve

serve:          ## alias for run
	uv run codegraph serve

snapshot-update:  ## regenerate contract snapshots
	uv run pytest tests/contract --snapshot-update