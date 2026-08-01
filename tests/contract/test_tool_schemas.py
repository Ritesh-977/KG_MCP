"""Golden snapshot: tools/list JSON must match committed snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

_SNAP = Path(__file__).resolve().parent / "__snapshots__" / "tool_schemas.json"


def _registered_tools() -> list[dict[str, str]]:
    """Return a sorted list of {name, description} for every registered tool."""
    from codegraph.server import mcp

    tools: list[dict[str, str]] = []
    tm = getattr(mcp, "_tool_manager", None)
    if tm is not None:
        registry = getattr(tm, "_tools", {}) or {}
        for name, tool in registry.items():
            tools.append(
                {
                    "name": name,
                    "description": (tool.description or "").strip(),
                }
            )
    return sorted(tools, key=lambda t: t["name"])


def test_tools_list_matches_snapshot(request: pytest.FixtureRequest) -> None:
    """The set of tools and their descriptions must match the committed snapshot.

    If you intentionally changed a tool's schema, regenerate with:
      uv run pytest tests/contract/test_tool_schemas.py --snapshot-update
    """
    tools = _registered_tools()
    if not tools:
        pytest.skip("tool manager not accessible — cannot introspect tools/list")
    snap = json.loads(_SNAP.read_text()) if _SNAP.exists() else None
    update = bool(request.config.getoption("snapshot_update", default=False))
    if snap is None or update:
        _SNAP.parent.mkdir(parents=True, exist_ok=True)
        _SNAP.write_text(json.dumps(tools, indent=2, sort_keys=True))
        if update:
            return  # refreshed — pass
        if snap is None:
            pytest.fail("snapshot did not exist; wrote baseline — review and re-run")
    assert tools == snap, (
        "tools/list drifted; run `uv run pytest tests/contract --snapshot-update` and review. Diff:\n"
        + json.dumps(tools, indent=2, sort_keys=True)
    )


def test_expected_tool_names_present() -> None:
    """All 6 tools must be registered."""
    from codegraph.server import mcp

    tm = getattr(mcp, "_tool_manager", None)
    if tm is None:
        pytest.skip("tool manager not accessible")
    names: set[str] = set(getattr(tm, "_tools", {}).keys()) or set()
    expected = {
        "list_repos",
        "init_repository_node",
        "get_repo_structure",
        "find_file_dependencies",
        "search_nodes",
        "get_node_detail",
    }
    assert expected.issubset(names), f"missing tools: {expected - names}"
