import heapq
from collections import defaultdict
from pathlib import Path


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def _is_test_path(path: str) -> bool:
    p = (path or "").lower()
    return "test" in Path(p).name or "/tests/" in f"/{p}"


def read_symbol(db, root, ref, token_budget=1500, context_lines=2) -> str:
    """Return just the symbol's source (with location), not the whole file."""
    node = db.node_by_ref(ref)
    if node is None:
        return (f"No node found for '{ref}'. "
                "Use cgraphy_search to find the right qualified name.")
    path = Path(root) / node["file_path"]
    try:
        lines = path.read_text(errors="replace").split("\n")
    except OSError:
        return f"{node['qualified_name']}: source file unavailable."
    start = max((node["line_start"] or 1) - 1 - context_lines, 0)
    end = min(node["line_end"] or len(lines), len(lines))
    header = (f"{node['kind']} {node['qualified_name']} — "
              f"{node['file_path']}:{node['line_start']}\n")
    budget_chars = token_budget * 4 - len(header) - 40
    body = []
    used = 0
    for i in range(start, min(end + context_lines, len(lines))):
        ln = f"{i + 1:>5}| {lines[i]}\n"
        if used + len(ln) > budget_chars:
            body.append("…(budget reached)\n")
            break
        body.append(ln)
        used += len(ln)
    return header + "".join(body)


def impact(db, ref, token_budget=1500, max_depth=3) -> str:
    """Blast radius: what depends on this symbol, and which tests cover it."""
    node = db.node_by_ref(ref)
    if node is None:
        return (f"No node found for '{ref}'. "
                "Use cgraphy_search to find the right qualified name.")
    budget = token_budget * 4
    # reverse BFS over incoming dependency edges
    dependents, tests = [], []
    seen = {node["id"]}
    frontier = [(node["id"], 0)]
    while frontier:
        nid, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        for direction, kind, _w, nrow in db.neighbors(nid):
            if direction != "in" or kind not in ("calls", "imports", "inherits"):
                continue
            if nrow["id"] in seen:
                continue
            seen.add(nrow["id"])
            entry = (depth + 1, nrow)
            (tests if _is_test_path(nrow["file_path"]) else dependents).append(entry)
            frontier.append((nrow["id"], depth + 1))
    dependents.sort(key=lambda e: (e[0], -(e[1]["rank"] or 0)))
    tests.sort(key=lambda e: (e[0], -(e[1]["rank"] or 0)))
    # co-changed files of the symbol's file
    cochanged = []
    frow = db.node_by_ref(node["file_path"]) if node["file_path"] else None
    if frow is not None:
        for _d, kind, w, nrow in db.neighbors(frow["id"]):
            if kind == "co_changes":
                cochanged.append((w, nrow["file_path"]))
        cochanged.sort(reverse=True)

    parts = [f"Impact of changing {node['kind']} {node['qualified_name']} "
             f"({node['file_path']}:{node['line_start']}):\n"]
    if dependents:
        parts.append(f"Dependents ({len(dependents)}, by distance):")
        parts += [f"  d{d} {_line(r)}" for d, r in dependents[:20]]
    else:
        parts.append("No known dependents (leaf symbol or unresolved callers).")
    if tests:
        parts.append(f"Tests likely affected ({len(tests)}):")
        parts += [f"  d{d} {_line(r)}" for d, r in tests[:10]]
    if cochanged:
        parts.append("Files that historically co-change with this file:")
        parts += [f"  {w:.2f} {p}" for w, p in cochanged[:8]]
    text = ""
    for p in parts:
        if len(text) + len(p) + 1 > budget:
            text += "…(budget reached)"
            break
        text += p + "\n"
    return text


def _line(row, prefix=""):
    loc = f"{row['file_path']}:{row['line_start']}" if row["line_start"] else row["file_path"]
    desc = row["summary"] or row["signature"] or ""
    return f"{prefix}{row['kind']} {row['qualified_name']} — {loc} — {desc}".rstrip(" —")


def overview(db, token_budget=2000) -> str:
    budget = token_budget * 4
    files = db.file_nodes()
    parts = [f"# Repository graph: {db.count_nodes()} nodes, {len(files)} files\n"]
    parts.append("## Key symbols (by importance)")
    for row in db.top_nodes(15):
        parts.append(_line(row, "- "))
    parts.append("\n## Files")
    groups = defaultdict(list)
    for f in files:
        top = f["file_path"].split("/")[0] if "/" in f["file_path"] else "."
        groups[top].append(f)
    for top in sorted(groups):
        parts.append(f"### {top}/")
        for f in groups[top]:
            desc = f" — {f['summary']}" if f["summary"] else ""
            parts.append(f"- {f['file_path']}{desc}")
    text = ""
    for p in parts:
        if len(text) + len(p) + 1 > budget:
            text += "…(truncated)"
            break
        text += p + "\n"
    return text


def search(db, query, limit=12) -> str:
    rows = db.search_fts(query, limit)
    if not rows:
        return f"No matches for '{query}'. Try different words or cgraphy_overview."
    return "\n".join(_line(r, "- ") for r in rows)


def context(db, ref, token_budget=2000) -> str:
    budget = token_budget * 4
    node = db.node_by_ref(ref)
    if node is None:
        return (f"No node found for '{ref}'. "
                "Use cgraphy_search to find the right qualified name.")
    header = [_line(node), ""]
    if node["signature"]:
        header.insert(1, f"signature: {node['signature']}")
    unresolved = [r["target_name"] for r in db.refs_from(node["id"])]
    text = "\n".join(header) + "\n"

    seen = {node["id"]}
    heap = []
    counter = 0
    for direction, kind, weight, nrow in db.neighbors(node["id"]):
        prio = weight * (0.5 + (nrow["rank"] or 0.0))
        counter += 1
        heapq.heappush(heap, (-prio, counter, 1, direction, kind, nrow))
    while heap:
        negp, _, depth, direction, kind, row = heapq.heappop(heap)
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        rel = {"out": kind, "in": f"{kind}-by"}[direction]
        line = _line(row, f"[{rel}] ") + "\n"
        if len(text) + len(line) > budget - 40:
            text += "…(budget reached)\n"
            break
        text += line
        if depth < 2:
            decay = 0.6 ** depth
            for d2, k2, w2, n2 in db.neighbors(row["id"]):
                if n2["id"] not in seen:
                    counter += 1
                    prio = w2 * (0.5 + (n2["rank"] or 0.0)) * decay
                    heapq.heappush(heap, (-prio, counter, depth + 1, d2, k2, n2))
    if unresolved:
        tail = "unresolved: " + ", ".join(sorted(set(unresolved))[:10]) + "\n"
        if len(text) + len(tail) <= budget:
            text += tail
    return text
