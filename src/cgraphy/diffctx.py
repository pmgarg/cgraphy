"""cgraphy_diff_context — the review-time tool.

Maps the current working diff (unstaged + staged) to the symbols whose line
ranges were touched, then reports each symbol's immediate blast radius so an
agent reviewing or extending the change sees exactly what it affects.
"""
import re
import subprocess
from collections import defaultdict

from cgraphy.graphq import _is_test_path, _line, estimate_tokens

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)
FILE_RE = re.compile(r"^diff --git a/\S+ b/(\S+)", re.M)


def _changed_ranges(root):
    """{path: [(start,end), ...]} for unstaged+staged changes vs HEAD."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "HEAD", "--unified=0"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if out.returncode != 0:
        return {}
    ranges = defaultdict(list)
    path = None
    for line in out.stdout.splitlines():
        m = FILE_RE.match(line)
        if m:
            path = m.group(1)
            continue
        m = HUNK_RE.match(line)
        if m and path:
            start = int(m.group(1))
            count = int(m.group(2) or 1)
            ranges[path].append((start, max(start + count - 1, start)))
    return dict(ranges)


def diff_context(db, root, token_budget=2000) -> str:
    budget = token_budget * 4
    ranges = _changed_ranges(root)
    if not ranges:
        return ("No uncommitted changes found (or not a git repository) — "
                "nothing to analyze.")
    parts = [f"Working diff touches {len(ranges)} file(s).\n"]
    for path, spans in ranges.items():
        touched = []
        for row in db.nodes_for_file(path):
            if row["kind"] == "file" or not row["line_start"]:
                continue
            for s, e in spans:
                if row["line_start"] <= e and s <= row["line_end"]:
                    touched.append(row)
                    break
        if not touched:
            parts.append(f"{path}: changed (no indexed symbols touched — "
                         "re-run cgraphy index if this looks wrong)")
            continue
        parts.append(f"{path}:")
        for row in touched:
            parts.append(f"  changed {_line(row)}")
            deps, tests = [], []
            for direction, kind, _w, nrow in db.neighbors(row["id"]):
                if direction == "in" and kind in ("calls", "imports", "inherits"):
                    (tests if _is_test_path(nrow["file_path"]) else deps).append(nrow)
            for n in deps[:5]:
                parts.append(f"    used-by {_line(n)}")
            for n in tests[:3]:
                parts.append(f"    test {_line(n)}")
    text = ""
    for p in parts:
        if len(text) + len(p) + 1 > budget:
            text += "…(budget reached)"
            break
        text += p + "\n"
    return text
