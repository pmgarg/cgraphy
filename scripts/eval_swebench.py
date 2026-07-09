"""End-to-end localization on SWE-bench Lite instances.

For each instance: check out the repo at base_commit, index it with cgraphy,
use the GitHub issue text (problem_statement) as the query, and score how
well each retrieval method surfaces the files modified by the gold patch.

Unlike the commit-subject benchmark, queries here are REAL user-written bug
reports, and the graph is built at the exact pre-fix snapshot the agent
would see. Co-change mining uses only history reachable from base_commit,
so the fix itself can never leak.

Usage:
  uv run python scripts/eval_swebench.py LITE_JSON CLONES_DIR repo1 repo2 ...
where LITE_JSON is the SWE-bench Lite test split as a JSON list and
CLONES_DIR contains clones named after each repo's basename.
"""
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from cgraphy.db import GraphDB
from cgraphy.gitmine import mine_cochanges
from cgraphy.indexer import db_path, index_repo
from cgraphy.pagerank import apply_pagerank

sys.path.insert(0, str(Path(__file__).parent))
from eval_localization import is_code, method_expand, method_fts, method_rank

PATCH_FILE_RE = re.compile(r"^diff --git a/(\S+) b/", re.M)


def patch_files(patch: str):
    return [f for f in PATCH_FILE_RE.findall(patch) if is_code(f)]


def make_query(problem: str, max_words=120):
    text = re.sub(r"```.*?```", " ", problem, flags=re.S)  # drop code blocks
    words = text.split()
    return " ".join(words[:max_words])


def checkout(repo: Path, sha: str) -> bool:
    r = subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-f", sha],
                       capture_output=True, timeout=120)
    subprocess.run(["git", "-C", str(repo), "clean", "-qfdx",
                    "-e", ".cgraphy"], capture_output=True, timeout=120)
    return r.returncode == 0


def run_instance(repo: Path, inst):
    if not checkout(repo, inst["base_commit"]):
        return None
    shutil.rmtree(repo / ".cgraphy", ignore_errors=True)
    index_repo(repo)
    db = GraphDB(db_path(repo))
    # history reachable from base_commit only — the fix cannot leak
    mine_cochanges(db, repo, max_commits=3000)
    apply_pagerank(db)
    q = make_query(inst["problem_statement"])
    out = {
        "fts": method_fts(db, q),
        "rank": method_rank(db, q),
        "expand-nc": method_expand(db, q, use_cochange=False),
        "expand": method_expand(db, q),
    }
    db.close()
    return out


def main():
    lite = json.load(open(sys.argv[1]))
    clones = Path(sys.argv[2])
    repos = set(sys.argv[3:])
    agg = defaultdict(lambda: {"hit5": 0.0, "hit10": 0.0, "rr": 0.0,
                               "tok": 0.0, "n": 0})
    per_repo = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    done = skipped = 0
    for inst in lite:
        name = inst["repo"].split("/")[-1]
        if name not in repos:
            continue
        repo = clones / name
        gt = set(patch_files(inst["patch"]))
        if not repo.is_dir() or not gt:
            skipped += 1
            continue
        res = run_instance(repo, inst)
        if res is None:
            skipped += 1
            continue
        done += 1
        for method, (files, tokens) in res.items():
            a = agg[method]
            first = next((i for i, f in enumerate(files) if f in gt), None)
            if first is not None:
                a["rr"] += 1.0 / (first + 1)
                a["hit5"] += first < 5
                a["hit10"] += first < 10
                per_repo[name][method][0] += first < 10
            a["tok"] += tokens
            a["n"] += 1
            per_repo[name][method][1] += 1
        print(f"  {inst['instance_id']}: done ({done})", flush=True)

    print(f"\nSWE-bench Lite localization — {done} instances "
          f"({skipped} skipped)")
    hdr = f"{'method':<10} {'hit@5':>6} {'hit@10':>7} {'mrr':>6} {'tokens':>7}"
    print(hdr + "\n" + "-" * len(hdr))
    summary = {}
    for m in ("fts", "rank", "expand-nc", "expand"):
        a = agg[m]
        n = a["n"] or 1
        summary[m] = {"hit@5": round(a["hit5"] / n, 3),
                      "hit@10": round(a["hit10"] / n, 3),
                      "mrr": round(a["rr"] / n, 3),
                      "avg_tokens": int(a["tok"] / n)}
        r = summary[m]
        print(f"{m:<10} {r['hit@5']:>6} {r['hit@10']:>7} {r['mrr']:>6} "
              f"{r['avg_tokens']:>7}")
    print("\nper-repo hit@10 (expand):",
          {k: round(v['expand'][0] / v['expand'][1], 2)
           for k, v in per_repo.items()})
    print("\nJSON:", json.dumps({"instances": done, "results": summary}))


if __name__ == "__main__":
    main()
