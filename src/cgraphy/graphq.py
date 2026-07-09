import heapq
from collections import defaultdict


def estimate_tokens(text: str) -> int:
    return len(text) // 4


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
