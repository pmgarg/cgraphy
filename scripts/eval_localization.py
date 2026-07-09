"""Commit-derived file-localization benchmark for cgraphy.

For each recent 'fix-like' commit in a repo, the commit subject becomes the
query and the files it touched become ground truth. We measure how well each
retrieval method surfaces those files, and what it costs in tokens.

Methods (ablation ladder):
  fts        FTS5 bm25 only (lexical baseline)
  rank       bm25 blended with PageRank (cgraphy_search default)
  expand     rank + one-hop graph expansion from top hits (all edges)
  expand-nc  same as expand but ignoring co_changes edges

Leakage control: co-change edges are mined EXCLUDING the evaluated commits.

Usage: uv run python scripts/eval_localization.py /path/to/repo [n_tasks]
Emits a summary table and a JSON blob for the paper.
"""
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from cgraphy.db import GraphDB, _fts_query
from cgraphy.gitmine import commit_blocks, mine_cochanges
from cgraphy.graphq import estimate_tokens, search
from cgraphy.indexer import db_path, index_repo
from cgraphy.pagerank import apply_pagerank
from cgraphy.walker import LANGUAGE_BY_EXT

FIX_RE = re.compile(r"\b(fix|bug|crash|error|fail|regress|broken|incorrect|"
                    r"wrong|issue|resolve)\w*\b", re.I)
CODE_EXTS = set(LANGUAGE_BY_EXT)


def is_code(path: str) -> bool:
    return Path(path).suffix.lower() in CODE_EXTS


def mine_tasks(repo, n_tasks, max_commits=3000):
    tasks = []
    for sha, subject, files in commit_blocks(repo, max_commits) or []:
        code = [f for f in files if is_code(f)]
        if not (1 <= len(code) <= 5) or len(files) > 10:
            continue
        subject = re.sub(r"\(?#\d+\)?", "", subject).strip()
        if len(subject.split()) < 3 or not FIX_RE.search(subject):
            continue
        # ground truth restricted to files that still exist at HEAD
        gt = [f for f in code if (Path(repo) / f).is_file()]
        if gt:
            tasks.append({"sha": sha, "query": subject, "gt": gt})
        if len(tasks) >= n_tasks:
            break
    return tasks


def ranked_files(rows):
    seen, out = set(), []
    for r in rows:
        fp = r["file_path"]
        if fp and fp not in seen:
            seen.add(fp)
            out.append(fp)
    return out


def method_fts(db, query, limit=25):
    rows = db.conn.execute(
        "SELECT n.* FROM node_fts JOIN nodes n ON n.id=node_fts.rowid "
        "WHERE node_fts MATCH ? ORDER BY bm25(node_fts) LIMIT ?",
        (_fts_query(query), limit)).fetchall()
    return ranked_files(rows), estimate_tokens(search(db, query))


def method_rank(db, query, limit=25):
    rows = db.search_fts(query, limit)
    return ranked_files(rows), estimate_tokens(search(db, query))


def method_expand(db, query, use_cochange=True, limit=25):
    rows = db.search_fts(query, limit)
    direct = ranked_files(rows)
    scores = defaultdict(float)
    for hit in rows[:5]:
        for _dir, kind, weight, nrow in db.neighbors(hit["id"]):
            if kind == "co_changes" and not use_cochange:
                continue
            fp = nrow["file_path"]
            if fp and fp not in direct:
                scores[fp] += weight * (0.5 + (nrow["rank"] or 0.0))
    expanded = [fp for fp, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
    tokens = estimate_tokens(search(db, query))
    if rows:
        from cgraphy.graphq import context
        tokens += estimate_tokens(context(db, rows[0]["qualified_name"], 1000))
    return direct + expanded, tokens


def score(tasks, retrieve):
    hit5 = hit10 = rr = tok = 0.0
    for t in tasks:
        files, tokens = retrieve(t["query"])
        tok += tokens
        gt = set(t["gt"])
        first = next((i for i, f in enumerate(files) if f in gt), None)
        if first is not None:
            rr += 1.0 / (first + 1)
            if first < 5:
                hit5 += 1
            if first < 10:
                hit10 += 1
    n = len(tasks)
    return {"hit@5": round(hit5 / n, 3), "hit@10": round(hit10 / n, 3),
            "mrr": round(rr / n, 3), "avg_tokens": int(tok / n)}


def main():
    repo = Path(sys.argv[1]).resolve()
    n_tasks = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    tasks = mine_tasks(repo, n_tasks)
    if len(tasks) < 10:
        print(f"only {len(tasks)} usable fix commits found; need >= 10")
        return
    print(f"{repo.name}: {len(tasks)} localization tasks")

    shutil.rmtree(repo / ".cgraphy", ignore_errors=True)
    index_repo(repo)  # no git history here — mined below with exclusions
    db = GraphDB(db_path(repo))
    mine_cochanges(db, repo, max_commits=3000,
                   exclude_shas={t["sha"] for t in tasks})
    apply_pagerank(db)

    results = {}
    results["fts"] = score(tasks, lambda q: method_fts(db, q))
    results["rank"] = score(tasks, lambda q: method_rank(db, q))
    results["expand-nc"] = score(
        tasks, lambda q: method_expand(db, q, use_cochange=False))
    results["expand"] = score(tasks, lambda q: method_expand(db, q))
    db.close()

    hdr = f"{'method':<10} {'hit@5':>6} {'hit@10':>7} {'mrr':>6} {'tokens':>7}"
    print(hdr)
    print("-" * len(hdr))
    for m, r in results.items():
        print(f"{m:<10} {r['hit@5']:>6} {r['hit@10']:>7} {r['mrr']:>6} "
              f"{r['avg_tokens']:>7}")
    print("\nJSON:", json.dumps({"repo": repo.name, "tasks": len(tasks),
                                 "results": results}))


if __name__ == "__main__":
    main()
