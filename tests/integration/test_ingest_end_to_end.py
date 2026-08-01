"""End-to-end: ingest the py_repo fixture, query the graph back."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "py_repo"


@pytest.mark.asyncio
async def test_ingest_fixture_writes_graph(adapter, fresh_graph_id) -> None:
    from codegraph.ingestion.graph_builder import build_ingest_plan, run_plan
    from codegraph.ingestion.python_parser import parse_python
    from codegraph.ingestion.walker import walk_repo

    entries = walk_repo(_FIXTURE)
    files = []
    for e in entries:
        if e.language == "py":
            files.append(parse_python(e.path, e.abspath.read_bytes()))
    known = {e.path for e in entries}
    plan = build_ingest_plan(
        slug=fresh_graph_id, url="https://github.com/test/py_repo", branch="main",
        files=files, commits={}, known_paths=known,
    )
    summary = await run_plan(adapter, plan)
    assert summary.files == len(files)
    # query back: auth.py exists and main.py IMPORTS auth.py
    rows = await adapter._run_read(
        "MATCH (f:File {graph_id: $gid, path: $p}) RETURN f.path AS p",
        gid=fresh_graph_id, p="auth.py",
    )
    assert rows
    imp = await adapter._run_read(
        "MATCH (src:File {graph_id: $gid, path: $src})-[:IMPORTS]->(tgt:File {graph_id: $gid, path: $tgt}) "
        "RETURN src.path AS s, tgt.path AS t",
        gid=fresh_graph_id, src="main.py", tgt="auth.py",
    )
    assert imp and imp[0]["s"] == "main.py" and imp[0]["t"] == "auth.py"
