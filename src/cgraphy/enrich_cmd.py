"""`cgraphy enrich` — automatic semantic enrichment via whatever agent CLI
is installed (claude, or the Anthropic API if a key is set).

No MCP round-trips: symbols are batched into one completion request each,
summaries come back as JSON and persist via content hashing, so re-running
after edits only pays for what changed. Importance-first, budget-capped.
"""
import json
import re
import subprocess
from pathlib import Path

from cgraphy import summarize
from cgraphy.db import GraphDB
from cgraphy.indexer import db_path

BATCH = 30

PROMPT = """Summarize each code symbol below in one line (<=15 words): what
it does and why it exists. Reply with ONLY a JSON array:
[{"id": <id>, "summary": "<text>"}, ...]

%s"""


def _claude_batch(blocks: str, model: str) -> list:
    r = subprocess.run(
        ["claude", "-p", PROMPT % blocks, "--output-format", "json",
         "--model", model, "--max-turns", "1"],
        capture_output=True, text=True, timeout=300)
    try:
        text = json.loads(r.stdout).get("result", "") or ""
    except ValueError:
        return []
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except ValueError:
        return []


def enrich_repo(root, max_nodes=400, model="claude-haiku-4-5-20251001",
                runner=_claude_batch) -> int:
    """Summarize up to max_nodes unsummarized symbols, importance-first."""
    root = Path(root).resolve()
    db = GraphDB(db_path(root))
    total = 0
    stalled = 0
    while total < max_nodes:
        rows = db.unsummarized(min(BATCH, max_nodes - total))
        if not rows:
            break
        blocks = "\n".join(
            f"--- id={r['id']} {r['kind']} {r['qualified_name']}\n"
            f"{summarize._snippet(root, r)}" for r in rows)
        items = runner(blocks, model)
        result = summarize.store_summaries(db, root, items)
        stored = int(result.split()[1])
        total += stored
        if stored == 0:
            stalled += 1
            if stalled >= 2:
                break
        else:
            stalled = 0
    db.close()
    return total
