"""Python AST parser → ExtractedFile. No I/O except reading bytes (caller does)."""

from __future__ import annotations

import ast

from codegraph.models.ingestion import (
    ExtractedCall,
    ExtractedFile,
    ExtractedFunction,
    ExtractedImport,
)


def parse_python(path: str, source: bytes) -> ExtractedFile:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        # Malformed source — return an empty ExtractedFile so the ingest
        # pipeline can skip this file without crashing the whole batch.
        return ExtractedFile(path=path, language="py")
    functions: list[ExtractedFunction] = []
    imports: list[ExtractedImport] = []
    calls: list[ExtractedCall] = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._stack: list[str] = []

        def _qname(self, name: str) -> str:
            return ".".join([*self._stack, name]) if self._stack else name

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            q = self._qname(node.name)
            functions.append(ExtractedFunction(
                name=node.name, qualified_name=q, kind="class",
                start_line=node.lineno, end_line=getattr(node, "end_lineno", node.lineno),
            ))
            self._stack.append(node.name)
            self.generic_visit(node)
            self._stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._handle_func(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._handle_func(node)

        def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            kind = "method" if self._stack else "function"
            q = self._qname(node.name)
            functions.append(ExtractedFunction(
                name=node.name, qualified_name=q, kind=kind,
                start_line=node.lineno, end_line=getattr(node, "end_lineno", node.lineno),
            ))
            self._stack.append(node.name)
            self.generic_visit(node)
            self._stack.pop()

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                imports.append(ExtractedImport(module=alias.name, symbol="", resolved_path=None))

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            # Preserve relative-import level so the resolver's relative branch fires.
            # `from .sub import x` → module=".sub"; `from . import x` → module="."
            mod = ("." * node.level) + (node.module or "")
            for alias in node.names:
                imports.append(ExtractedImport(module=mod, symbol=alias.name, resolved_path=None))

        def visit_Call(self, node: ast.Call) -> None:
            caller = ".".join(self._stack) if self._stack else "<module>"
            callee = _callee_name(node)
            if callee:
                calls.append(ExtractedCall(caller_qname=caller, callee_name=callee))
            self.generic_visit(node)

    _Visitor().visit(tree)
    return ExtractedFile(path=path, language="py", functions=functions, imports=imports, calls=calls)


def _callee_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""
