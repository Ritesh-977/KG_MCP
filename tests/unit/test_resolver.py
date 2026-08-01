# tests/unit/test_resolver.py
"""Pure-logic import-path resolution — no I/O."""

from __future__ import annotations

from codegraph.ingestion.resolver import (
    resolve_js_import,
    resolve_python_import,
)


def test_py_absolute_import_resolves_to_module_file() -> None:
    known = {"src/codegraph/ingestion/resolver.py", "src/codegraph/__init__.py"}
    assert resolve_python_import("codegraph.ingestion.resolver", "src/main.py", known) == "src/codegraph/ingestion/resolver.py"


def test_py_package_import_resolves_to_init() -> None:
    known = {"src/codegraph/__init__.py"}
    assert resolve_python_import("codegraph", "src/main.py", known) == "src/codegraph/__init__.py"


def test_py_stdlib_not_resolved() -> None:
    assert resolve_python_import("os.path", "src/main.py", {"src/main.py"}) is None


def test_py_relative_import_resolves() -> None:
    known = {"pkg/sub/mod.py", "pkg/__init__.py"}
    assert resolve_python_import(".sub.mod", "pkg/__init__.py", known) == "pkg/sub/mod.py"


def test_js_relative_import_resolves_with_extension() -> None:
    known = {"src/auth.js", "src/index.js"}
    assert resolve_js_import("./auth", "src/index.js", known) == "src/auth.js"


def test_js_relative_import_resolves_index() -> None:
    known = {"src/utils/index.ts"}
    assert resolve_js_import("./utils", "src/main.ts", known) == "src/utils/index.ts"


def test_js_external_not_resolved() -> None:
    assert resolve_js_import("react", "src/main.ts", {"src/main.ts"}) is None
