"""`cgraphy init` — wire cgraphy into every AI assistant surface for a repo.

Creates project-scoped MCP config (.mcp.json — read by Claude Code CLI, the
Claude Code VSCode extension, and the desktop app) and appends a steering
block to CLAUDE.md and AGENTS.md so agents actually prefer the graph over
reading whole files. Prints setup lines for surfaces that need user-level
config (Codex, Gemini, Cursor, Claude Desktop).
"""
import json
from pathlib import Path

STEERING_MARK = "<!-- cgraphy-steering -->"

STEERING_BLOCK = f"""
{STEERING_MARK}
## Code navigation: use the cgraphy knowledge graph

This repo is indexed by cgraphy (MCP server `cgraphy`). To keep context small
and answers grounded, follow this order BEFORE reading files:

1. `cgraphy_overview` — orient yourself (repo map, subsystems, key symbols).
2. `cgraphy_search <query>` — locate symbols/files by name or meaning.
3. `cgraphy_context <symbol>` — callers/callees/imports/co-changed files
   within a token budget.
4. `cgraphy_read <symbol>` — read just that symbol's source, not the file.

When EDITING code:
- BEFORE changing a shared symbol, call `cgraphy_impact <symbol>` to see
  dependents and affected tests.
- BEFORE committing (or when resuming work), call `cgraphy_diff_context`
  to map your working diff to affected symbols and tests.

Do NOT bulk-read directories or many whole files when these tools can answer
structurally. If summaries are missing, run the `cgraphy_enrich` →
`cgraphy_store_summaries` loop once when idle.
"""

MCP_ENTRY = {"command": "uvx", "args": ["cgraphy", "serve", "."]}

OTHER_SURFACES = """\
.mcp.json written — picked up automatically by Claude Code (CLI, VSCode
extension, and desktop app) for this project.

Other surfaces (one-time, user-level config):
  Codex CLI / Codex VSCode extension (~/.codex/config.toml):
      [mcp_servers.cgraphy]
      command = "uvx"
      args = ["cgraphy", "serve", "{root}"]
  Gemini CLI (~/.gemini/settings.json) and Cursor (.cursor/mcp.json):
      {{"mcpServers": {{"cgraphy": {{"command": "uvx",
        "args": ["cgraphy", "serve", "{root}"]}}}}}}
  Claude Desktop (claude_desktop_config.json, Settings > Developer):
      same JSON shape as Gemini/Cursor.

Steering appended to CLAUDE.md and AGENTS.md (Codex and most agents read
AGENTS.md; for Gemini CLI copy the block into GEMINI.md if you use one).
"""


def _append_steering(path: Path):
    text = path.read_text(errors="replace") if path.is_file() else ""
    if STEERING_MARK in text:
        return
    sep = "\n" if not text or text.endswith("\n") else "\n\n"
    path.write_text(text + sep + STEERING_BLOCK.lstrip("\n"))


def _write_mcp_json(root: Path):
    p = root / ".mcp.json"
    data = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text())
        except ValueError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    servers["cgraphy"] = MCP_ENTRY
    p.write_text(json.dumps(data, indent=2) + "\n")


def init_project(root) -> str:
    root = Path(root).resolve()
    _write_mcp_json(root)
    for name in ("CLAUDE.md", "AGENTS.md"):
        _append_steering(root / name)
    return OTHER_SURFACES.format(root=root)
