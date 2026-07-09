import time
from pathlib import Path

from cgraphy import graphq, summarize
from cgraphy.db import GraphDB
from cgraphy.indexer import db_path, index_repo

_last_check = 0.0
STALE_SECONDS = 30


def _fresh_db(root: Path, auto_create=False):
    """Incrementally refresh if stale; return GraphDB or None."""
    global _last_check
    exists = db_path(root).exists()
    if not exists and not auto_create:
        return None
    now = time.time()
    if not exists or now - _last_check > STALE_SECONDS:
        try:
            index_repo(root)
        except Exception:
            pass
        _last_check = now
    return GraphDB(db_path(root))


NO_GRAPH = ("No graph found — call cgraphy_overview first "
            "(it builds the index automatically) or run `cgraphy index`.")


def make_tools(root):
    root = Path(root).resolve()

    def cgraphy_overview() -> str:
        db = _fresh_db(root, auto_create=True)
        try:
            return graphq.overview(db)
        finally:
            db.close()

    def cgraphy_search(query: str) -> str:
        db = _fresh_db(root)
        if db is None:
            return NO_GRAPH
        try:
            return graphq.search(db, query)
        finally:
            db.close()

    def cgraphy_context(symbol_or_file: str, token_budget: int = 2000) -> str:
        db = _fresh_db(root)
        if db is None:
            return NO_GRAPH
        try:
            return graphq.context(db, symbol_or_file, token_budget=token_budget)
        finally:
            db.close()

    def cgraphy_enrich() -> str:
        db = _fresh_db(root)
        if db is None:
            return NO_GRAPH
        try:
            return summarize.enrich_batch(db, root)
        finally:
            db.close()

    def cgraphy_store_summaries(items: list[dict]) -> str:
        db = _fresh_db(root)
        if db is None:
            return NO_GRAPH
        try:
            return summarize.store_summaries(db, root, items)
        finally:
            db.close()

    def cgraphy_read(symbol_or_file: str, token_budget: int = 1500) -> str:
        db = _fresh_db(root)
        if db is None:
            return NO_GRAPH
        try:
            return graphq.read_symbol(db, root, symbol_or_file,
                                      token_budget=token_budget)
        finally:
            db.close()

    def cgraphy_impact(symbol: str, token_budget: int = 1500) -> str:
        db = _fresh_db(root)
        if db is None:
            return NO_GRAPH
        try:
            return graphq.impact(db, symbol, token_budget=token_budget)
        finally:
            db.close()

    def cgraphy_diff_context(token_budget: int = 2000) -> str:
        db = _fresh_db(root)
        if db is None:
            return NO_GRAPH
        try:
            from cgraphy.diffctx import diff_context
            return diff_context(db, root, token_budget=token_budget)
        finally:
            db.close()

    return {
        "cgraphy_overview": cgraphy_overview,
        "cgraphy_search": cgraphy_search,
        "cgraphy_context": cgraphy_context,
        "cgraphy_read": cgraphy_read,
        "cgraphy_impact": cgraphy_impact,
        "cgraphy_diff_context": cgraphy_diff_context,
        "cgraphy_enrich": cgraphy_enrich,
        "cgraphy_store_summaries": cgraphy_store_summaries,
    }


DESCRIPTIONS = {
    "cgraphy_overview":
        "ALWAYS call this FIRST before exploring files in this repo. Returns a "
        "compact map of the codebase: key symbols ranked by importance and all "
        "files with summaries. Replaces reading many files to orient yourself.",
    "cgraphy_search":
        "Search the code knowledge graph by meaning or name (functions, classes, "
        "files). Use BEFORE grep/file reads — results include semantic summaries "
        "and exact file:line locations.",
    "cgraphy_context":
        "Get the relevant subgraph around one symbol or file: its signature, "
        "summary, callers, callees, imports and co-changed files — within a "
        "token budget. Use instead of reading whole files; then read only the "
        "1-2 files that matter.",
    "cgraphy_read":
        "Read ONLY the source of one symbol (function/class) with line "
        "numbers, within a token budget. Use instead of reading whole files "
        "once cgraphy_search or cgraphy_context located the symbol.",
    "cgraphy_impact":
        "Blast radius BEFORE editing a symbol: everything that depends on it "
        "(direct and transitive callers/importers), tests likely affected, "
        "and files that historically change together with it. ALWAYS call "
        "this before modifying or refactoring shared code.",
    "cgraphy_diff_context":
        "Review the current uncommitted changes: maps the working git diff "
        "to the exact symbols touched and shows what uses them and which "
        "tests cover them. Call before committing or when asked to review "
        "or continue in-progress work.",
    "cgraphy_enrich":
        "Fetch code symbols that still need one-line summaries. Summarize each "
        "and submit via cgraphy_store_summaries; repeat until done. Run this "
        "when idle or when asked to 'enrich the graph'.",
    "cgraphy_store_summaries":
        "Store one-line summaries for symbol ids returned by cgraphy_enrich. "
        "items=[{'id': 1, 'summary': 'validates JWT expiry'}, ...]",
}


def create_server(root):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("cgraphy")
    tools = make_tools(root)
    for name, fn in tools.items():
        mcp.add_tool(fn, name=name, description=DESCRIPTIONS[name])
    return mcp


def run_server(root):
    create_server(root).run()
