"""tree-sitter JS/TS parser — functions + imports + calls."""

from __future__ import annotations

from codegraph.ingestion.jsts_parser import parse_jsts

_TS_SOURCE = b'''
import { authenticate } from "./auth";

export function main(): void {
  if (authenticate("admin")) {
    console.log("ok");
  }
}

class UserService {
  get(uid: number): boolean { return true; }
}
'''


def test_extracts_function() -> None:
    ef = parse_jsts("svc.ts", _TS_SOURCE, "ts")
    names = {f.name for f in ef.functions}
    assert "main" in names


def test_extracts_class() -> None:
    ef = parse_jsts("svc.ts", _TS_SOURCE, "ts")
    assert any(f.kind == "class" and f.name == "UserService" for f in ef.functions)


def test_extracts_import() -> None:
    ef = parse_jsts("svc.ts", _TS_SOURCE, "ts")
    assert any(i.module == "./auth" and i.symbol == "authenticate" for i in ef.imports)


def test_extracts_call() -> None:
    ef = parse_jsts("svc.ts", _TS_SOURCE, "ts")
    callees = {c.callee_name for c in ef.calls}
    assert "authenticate" in callees


def test_qualified_name_is_file_scoped() -> None:
    """Two files defining the same function name should NOT collide."""
    ef = parse_jsts("svc.ts", _TS_SOURCE, "ts")
    qnames = {f.qualified_name for f in ef.functions}
    assert "svc.ts::main" in qnames
    assert "svc.ts::UserService" in qnames


def test_caller_qname_traces_to_enclosing_function() -> None:
    """Calls inside a function should attribute caller_qname to that function."""
    ef = parse_jsts("svc.ts", _TS_SOURCE, "ts")
    # `authenticate("admin")` is called inside `main()` → caller should be svc.ts::main
    auth_calls = [c for c in ef.calls if c.callee_name == "authenticate"]
    assert auth_calls
    assert auth_calls[0].caller_qname == "svc.ts::main"
