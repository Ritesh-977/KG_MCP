"""Python ast parser — extract functions, imports, calls from fixture source."""

from __future__ import annotations

from codegraph.ingestion.python_parser import parse_python

_SOURCE = b'''
"""A module."""
import os
from auth import authenticate


class UserService:
    def get(self, uid: int) -> bool:
        return self.check(uid)

    def check(self, uid: int) -> bool:
        return True


def main() -> None:
    svc = UserService()
    if svc.get(1):
        print("ok")
'''


def test_extracts_top_level_function() -> None:
    ef = parse_python("svc.py", _SOURCE)
    names = {f.name for f in ef.functions}
    assert "main" in names


def test_extracts_class_and_methods() -> None:
    ef = parse_python("svc.py", _SOURCE)
    by_qname = {f.qualified_name: f for f in ef.functions}
    assert "UserService" in by_qname
    assert by_qname["UserService"].kind == "class"
    assert "UserService.get" in by_qname
    assert by_qname["UserService.get"].kind == "method"


def test_extracts_imports() -> None:
    ef = parse_python("svc.py", _SOURCE)
    assert any(i.module == "os" for i in ef.imports)
    assert any(i.module == "auth" and i.symbol == "authenticate" for i in ef.imports)


def test_extracts_calls_with_caller_qname() -> None:
    ef = parse_python("svc.py", _SOURCE)
    callers = {c.caller_qname for c in ef.calls}
    assert "UserService.get" in callers
    assert "main" in callers


def test_resolved_path_is_none_when_no_known_files() -> None:
    ef = parse_python("svc.py", _SOURCE)
    for imp in ef.imports:
        assert imp.resolved_path is None  # parser doesn't resolve; resolver does later


def test_relative_import_preserves_level_for_resolver() -> None:
    """`from .sub import x` must reach the resolver as `.sub` (not `sub`)."""
    src = b"from .sub import x\n"
    ef = parse_python("pkg/mod.py", src)
    assert len(ef.imports) == 1
    assert ef.imports[0].module == ".sub"
    # Round-trip through the resolver: should hit the relative branch
    from codegraph.ingestion.resolver import resolve_python_import
    known = {"pkg/sub/__init__.py", "pkg/__init__.py"}
    resolved = resolve_python_import(ef.imports[0].module, "pkg/mod.py", known)
    assert resolved == "pkg/sub/__init__.py"


def test_syntax_error_returns_empty_extracted_file() -> None:
    """Malformed source should not crash the parser — return an empty ExtractedFile."""
    bad = b"def broken(:\n"
    ef = parse_python("bad.py", bad)
    assert ef.path == "bad.py"
    assert ef.functions == []
    assert ef.imports == []
    assert ef.calls == []
