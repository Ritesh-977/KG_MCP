"""tree-sitter JS/TS/TSX parser → ExtractedFile.

Loads per-language grammar wheels and runs a single Query capturing
function/class/import/call nodes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser, Query, QueryCursor

from codegraph.models.ingestion import (
    ExtractedCall,
    ExtractedFile,
    ExtractedFunction,
    ExtractedImport,
)

_LANGS = {
    "js": lambda: Language(tsjs.language()),
    "ts": lambda: Language(tsts.language_typescript()),
    "tsx": lambda: Language(tsts.language_tsx()),
}

_QUERY = """
(function_declaration name: (identifier) @fn.name) @fn.def
(method_definition name: (property_identifier) @meth.name) @meth.def
(class_declaration name: (type_identifier) @cls.name) @cls.def
(import_statement) @imp.stmt
(call_expression function: (identifier) @call.name)
(call_expression function: (member_expression property: (property_identifier) @call.name))
"""


def parse_jsts(path: str, source: bytes, language: str) -> ExtractedFile:
    if language not in _LANGS:
        raise ValueError(f"unsupported language {language!r}")
    lang = _LANGS[language]()
    parser = Parser(lang)
    tree = parser.parse(source)
    q = Query(lang, _QUERY)
    cursor = QueryCursor(q)
    captures = cursor.captures(tree.root_node)

    functions: list[ExtractedFunction] = []
    imports: list[ExtractedImport] = []
    calls: list[ExtractedCall] = []

    for node in _cap(captures, "fn.name"):
        functions.append(_mk_func(node, source, "function", path))
    for node in _cap(captures, "meth.name"):
        functions.append(_mk_func(node, source, "method", path))
    for node in _cap(captures, "cls.name"):
        functions.append(_mk_func(node, source, "class", path))
    for imp_node in _cap(captures, "imp.stmt"):
        imports.extend(_imports_from(imp_node, source))
    for call_node in _cap(captures, "call.name"):
        caller = _find_enclosing_func(call_node, source, path)
        calls.append(ExtractedCall(caller_qname=caller, callee_name=_text(call_node, source)))

    return ExtractedFile(
        path=path, language=language, functions=functions, imports=imports, calls=calls
    )


def _cap(captures: Any, name: str) -> list[Any]:
    """Normalize the captures return across tree-sitter binding versions.

    ``QueryCursor.captures`` returns either a ``dict[str, list[Node]]`` (newer
    bindings) or a ``list[tuple[str, Node]]`` (older bindings / ``matches``).
    """
    if isinstance(captures, dict):
        return list(captures.get(name, []))
    return [n for k, n in captures if k == name]


def _text(node: Any, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _mk_func(name_node: Any, source: bytes, kind: str, file_path: str) -> ExtractedFunction:
    name = _text(name_node, source)
    # Scope qualified_name per-file to avoid cross-file collisions
    # (two files each defining `function authenticate` would otherwise MERGE
    # into one Function node).
    qualified = f"{file_path}::{name}"
    parent = name_node.parent
    start = (parent.start_point[0] + 1) if parent else (name_node.start_point[0] + 1)
    end = (parent.end_point[0] + 1) if parent else (name_node.end_point[0] + 1)
    return ExtractedFunction(
        name=name,
        qualified_name=qualified,
        kind=kind,
        start_line=start,
        end_line=end,
    )


def _imports_from(imp_node: Any, source: bytes) -> list[ExtractedImport]:
    """Best-effort: pull the string-literal source and the imported names."""
    out: list[ExtractedImport] = []
    mod = ""
    symbols: list[str] = []
    for child in imp_node.children:
        t = child.type
        if t == "import_clause":
            for sub in _walk(child):
                if sub.type == "identifier":
                    symbols.append(_text(sub, source))
        if t == "string":
            mod = _text(child, source).strip('"').strip("'")
    for sym in symbols:
        out.append(ExtractedImport(module=mod, symbol=sym, resolved_path=None))
    if not out and mod:
        out.append(ExtractedImport(module=mod, symbol="", resolved_path=None))
    return out


def _walk(node: Any) -> Iterator[Any]:
    yield node
    for c in node.children:
        yield from _walk(c)


def _find_enclosing_func(call_node: Any, source: bytes, file_path: str) -> str:
    """Walk ancestors of a call_expression to find the enclosing function/method.

    Returns the qualified_name of the enclosing function, or "<module>" if the
    call is at the top level (not inside any function).
    """
    node = call_node.parent
    while node is not None:
        ntype = node.type
        if ntype in ("function_declaration", "method_definition", "class_declaration"):
            # Find the name child
            for child in node.children:
                if child.type in ("identifier", "property_identifier", "type_identifier"):
                    name = _text(child, source)
                    return f"{file_path}::{name}"
        node = node.parent
    return "<module>"
