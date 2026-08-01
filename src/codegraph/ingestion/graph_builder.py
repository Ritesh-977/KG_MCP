"""Graph builder: turns ExtractedFiles into a list of (Cypher, params) statements.

Two-pass CALLS resolution: defines all :Function nodes first, then resolves
calls against the full known-qualified-name set in a final pass. Unresolved
imports/calls become :Symbol leaves (never phantom File/Function nodes).

Every Cypher statement is parameterized and filters on graph_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codegraph.ingestion.commits import CommitInfo
from codegraph.ingestion.resolver import resolve_js_import, resolve_python_import
from codegraph.models.ingestion import ExtractedFile


@dataclass
class IngestSummary:
    files: int
    functions: int
    imports: int
    calls: int
    external_symbols: int
    pruned: int


def build_ingest_plan(
    *,
    slug: str,
    url: str,
    branch: str,
    files: list[ExtractedFile],
    commits: dict[str, CommitInfo],
    known_paths: set[str],
) -> list[tuple[str, dict[str, Any]]]:
    """Build the ordered list of (Cypher, params) statements for ingestion."""
    plan: list[tuple[str, dict[str, Any]]] = []

    # 1. Repository node
    plan.append((
        "MERGE (r:Repository {graph_id: $gid}) "
        "SET r.name = $name, r.url = $url, r.default_branch = $branch, "
        "    r.ingested_at = datetime()",
        {"gid": slug, "name": slug, "url": url, "branch": branch},
    ))

    # 2. Files + CONTAINS + DEFINES + IMPORTS (pass 1)
    for ef in files:
        ci = commits.get(ef.path)
        set_clause = "f.language = $lang, f.deleted = false"
        params: dict[str, Any] = {"gid": slug, "path": ef.path, "lang": ef.language}
        if ci:
            set_clause += ", f.last_author = $author, f.last_commit_at = $date, f.last_commit_sha = $sha"
            params["author"] = ci.last_author
            params["date"] = ci.last_commit_at
            params["sha"] = ci.last_commit_sha
        plan.append((
            f"MERGE (f:File {{graph_id: $gid, path: $path}}) SET {set_clause}",
            params,
        ))
        plan.append((
            "MATCH (r:Repository {graph_id: $gid}), (f:File {graph_id: $gid, path: $path}) "
            "MERGE (r)-[:CONTAINS]->(f)",
            {"gid": slug, "path": ef.path},
        ))
        # functions
        for fn in ef.functions:
            plan.append((
                "MERGE (fn:Function {graph_id: $gid, qualified_name: $qn}) "
                "SET fn.name = $name, fn.kind = $kind, fn.start_line = $sl, fn.end_line = $el, fn.path = $fpath",
                {"gid": slug, "qn": fn.qualified_name, "name": fn.name,
                 "kind": fn.kind, "sl": fn.start_line, "el": fn.end_line, "fpath": ef.path},
            ))
            plan.append((
                "MATCH (f:File {graph_id: $gid, path: $path}), "
                "      (fn:Function {graph_id: $gid, qualified_name: $qn}) "
                "MERGE (f)-[:DEFINES]->(fn)",
                {"gid": slug, "path": ef.path, "qn": fn.qualified_name},
            ))
        # imports
        for imp in ef.imports:
            resolved = _resolve(imp.module, ef.path, ef.language, known_paths)
            if resolved:
                plan.append((
                    "MATCH (src:File {graph_id: $gid, path: $src}), "
                    "      (tgt:File {graph_id: $gid, path: $tgt}) "
                    "MERGE (src)-[:IMPORTS]->(tgt)",
                    {"gid": slug, "src": ef.path, "tgt": resolved},
                ))
            else:
                plan.append((
                    "MERGE (s:Symbol {graph_id: $gid, name: $name}) SET s.kind = 'import' "
                    "WITH s "
                    "MATCH (f:File {graph_id: $gid, path: $path}) "
                    "MERGE (f)-[:IMPORTS]->(s)",
                    {"gid": slug, "name": imp.module, "path": ef.path},
                ))

    # 3. CALLS resolution (pass 2) — needs all :Function nodes to exist
    all_qnames = {fn.qualified_name for ef in files for fn in ef.functions}
    for ef in files:
        for call in ef.calls:
            target_qn = _resolve_call(call.callee_name, all_qnames)
            if target_qn:
                plan.append((
                    "MATCH (caller:Function {graph_id: $gid, qualified_name: $cq}), "
                    "      (callee:Function {graph_id: $gid, qualified_name: $tq}) "
                    "MERGE (caller)-[:CALLS]->(callee)",
                    {"gid": slug, "cq": call.caller_qname, "tq": target_qn},
                ))
            else:
                plan.append((
                    "MERGE (s:Symbol {graph_id: $gid, name: $name}) SET s.kind = 'call' "
                    "WITH s "
                    "MATCH (caller:Function {graph_id: $gid, qualified_name: $cq}) "
                    "MERGE (caller)-[:CALLS]->(s)",
                    {"gid": slug, "name": call.callee_name, "cq": call.caller_qname},
                ))

    # 4. Prune tombstones for files no longer in the working tree
    plan.append((
        "MATCH (f:File {graph_id: $gid}) "
        "WHERE NOT f.path IN $paths AND f.deleted = false "
        "SET f.deleted = true "
        "WITH count(f) AS c RETURN c",
        {"gid": slug, "paths": list(known_paths)},
    ))

    return plan


def _resolve(module: str, current_file: str, language: str, known: set[str]) -> str | None:
    if language == "py":
        return resolve_python_import(module, current_file, known)
    return resolve_js_import(module, current_file, known)


def _resolve_call(callee_name: str, all_qnames: set[str]) -> str | None:
    """Naive: match any qualified_name ending in .<callee_name>, ::<callee_name>, or equal to it."""
    for qn in all_qnames:
        if qn == callee_name or qn.endswith("." + callee_name) or qn.endswith("::" + callee_name):
            return qn
    return None


async def run_plan(adapter: Any, plan: list[tuple[str, dict[str, Any]]]) -> IngestSummary:
    """Execute the plan against the adapter and return counts."""
    pruned = 0
    for cypher, params in plan:
        rows = await adapter._run_write(cypher, **params)
        # The prune statement returns a count via RETURN — capture it
        if "deleted = true" in cypher and rows:
            pruned = int(rows[0].get("c", 0)) if rows else 0
    files = sum(1 for c, _ in plan if "MERGE (f:File" in c)
    functions = sum(1 for c, _ in plan if "MERGE (fn:Function" in c)
    imports = sum(1 for c, _ in plan if "[:IMPORTS]" in c)
    calls = sum(1 for c, _ in plan if "[:CALLS]" in c)
    external_symbols = sum(1 for c, _ in plan if "MERGE (s:Symbol" in c)
    return IngestSummary(files=files, functions=functions, imports=imports,
                         calls=calls, external_symbols=external_symbols, pruned=pruned)
