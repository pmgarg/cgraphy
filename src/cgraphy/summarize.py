import hashlib
import json
import os
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


API_PROMPT = """Summarize each code symbol below in one line (<=15 words): \
what it does and why it exists.
Reply with ONLY a JSON array: [{"id": <id>, "summary": "<text>"}, ...]

%s"""


def _anthropic_client():
    try:
        import anthropic
    except ImportError:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic()


def api_summarize(db, root, model=None, batch=25) -> int:
    client = _anthropic_client()
    if client is None:
        print("--summarize needs `pip install cgraphy[summarize]` and "
              "ANTHROPIC_API_KEY; skipping (agents can enrich via MCP instead).")
        return 0
    model = model or os.environ.get("CGRAPHY_MODEL", "claude-haiku-4-5-20251001")
    total = 0
    while True:
        rows = db.unsummarized(batch)
        if not rows:
            break
        blocks = "\n".join(
            f"--- id={r['id']} {r['kind']} {r['qualified_name']}\n"
            f"{_snippet(root, r)}" for r in rows)
        resp = client.messages.create(
            model=model, max_tokens=2000,
            messages=[{"role": "user", "content": API_PROMPT % blocks}])
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`").lstrip("json\n")
        try:
            items = json.loads(text)
        except ValueError:
            break
        before = total
        result = store_summaries(db, root, items)
        total += int(result.split()[1])
        if total == before:  # no progress; avoid infinite loop
            break
    return total
