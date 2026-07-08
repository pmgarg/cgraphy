import hashlib
from pathlib import Path

MAX_SNIPPET_LINES = 60

INSTRUCTIONS = """\
Write a one-line summary (<=15 words) of WHAT each item does and WHY it exists.
Then call cgraphy_store_summaries with items=[{"id": <id>, "summary": "<text>"}, ...].
After storing, call cgraphy_enrich again and repeat until everything is summarized.
"""


def _snippet(root, row) -> str:
    p = Path(root) / row["file_path"]
    try:
        lines = p.read_text(errors="replace").split("\n")
    except OSError:
        return ""
    start = (row["line_start"] or 1) - 1
    end = row["line_end"] or len(lines)
    chunk = lines[start:min(end, start + MAX_SNIPPET_LINES)]
    return "\n".join(chunk) + "\n"


def enrich_batch(db, root, limit=20) -> str:
    rows = db.unsummarized(limit)
    if not rows:
        return (f"All {db.count_nodes()} nodes are summarized. "
                "The graph is fully enriched.")
    parts = [f"{len(rows)} symbols need summaries.\n", INSTRUCTIONS]
    for r in rows:
        parts.append(f"--- id={r['id']} {r['kind']} {r['qualified_name']} "
                     f"({r['file_path']}:{r['line_start']})")
        parts.append(_snippet(root, r) or "(source unavailable)")
    return "\n".join(parts)


def store_summaries(db, root, items) -> str:
    stored = 0
    for item in items or []:
        try:
            nid = int(item["id"])
            summary = str(item["summary"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        row = db.get_node(nid)
        if row is None or not summary:
            continue
        h = hashlib.sha256(_snippet(root, row).encode()).hexdigest()
        db.update_summary(nid, summary[:300], h)
        stored += 1
    db.commit()
    remaining = len(db.unsummarized(1000))
    return (f"Stored {stored} summaries. {remaining} symbols still need one — "
            + ("call cgraphy_enrich for the next batch." if remaining else
               "the graph is fully enriched."))
