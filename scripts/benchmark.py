"""Measure token cost of orienting in a repo: cgraphy vs raw file reading.

Usage: uv run python scripts/benchmark.py /path/to/repo "query string"
"""
import sys
from pathlib import Path

from cgraphy.db import GraphDB
from cgraphy.graphq import context, estimate_tokens, overview, search
from cgraphy.indexer import db_path, index_repo
from cgraphy.walker import iter_files


def main():
    repo = Path(sys.argv[1]).resolve()
    query = sys.argv[2] if len(sys.argv) > 2 else "main entry point"
    index_repo(repo)
    db = GraphDB(db_path(repo))

    graph_tokens = 0
    for name, out in [("overview", overview(db)), ("search", search(db, query))]:
        t = estimate_tokens(out)
        graph_tokens += t
        print(f"cgraphy_{name}: {t} tokens")
    hits = db.search_fts(query, 1)
    if hits:
        t = estimate_tokens(context(db, hits[0]["qualified_name"]))
        graph_tokens += t
        print(f"cgraphy_context: {t} tokens")

    raw_tokens = sum(
        estimate_tokens(p.read_text(errors="replace"))
        for p, lang in iter_files(repo) if lang is not None)
    print(f"\ncgraphy total:        {graph_tokens:>10,} tokens")
    print(f"reading all code:     {raw_tokens:>10,} tokens")
    if graph_tokens:
        print(f"reduction:            {raw_tokens / graph_tokens:>9.1f}x")
    db.close()


if __name__ == "__main__":
    main()
