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
## cgraphy knowledge graph (MCP server `cgraphy`)

This repo has a self-maintaining code graph. Tool names appear as
`mcp__cgraphy__<tool>` (e.g. `mcp__cgraphy__cgraphy_search`).

These are REPLACEMENTS, not extra steps — substitute, don't add:

| Instead of | Use |
| --- | --- |
| grep for a symbol/function/class name | `cgraphy_search <name or meaning>` |
| reading a whole file to see one function | `cgraphy_read <symbol>` |
| tracing callers/usages by hand | `cgraphy_context <symbol>` |
| guessing what a change breaks | `cgraphy_impact <symbol>` |
| re-reading your own diff before commit | `cgraphy_diff_context` |

Keep your normal workflow otherwise. Grep is still right for literal
strings, error messages, and non-symbol text. Never run the same lookup
through both paths. NEVER call cgraphy_enrich/cgraphy_store_summaries
unless the user explicitly asks to enrich the graph.
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


HOOK_MARK = "# cgraphy-diff-context"
HOOK_BODY = f"""{HOOK_MARK}
# Show blast radius of this commit (never blocks the commit).
uvx cgraphy diff . 2>/dev/null || true
"""


def _install_hook(root: Path) -> bool:
    hooks = root / ".git" / "hooks"
    if not hooks.is_dir():
        return False
    hook = hooks / "pre-commit"
    if hook.is_file():
        text = hook.read_text(errors="replace")
        if HOOK_MARK in text:
            return True
        hook.write_text(text.rstrip("\n") + "\n\n" + HOOK_BODY)
    else:
        hook.write_text("#!/bin/sh\n" + HOOK_BODY)
    hook.chmod(0o755)
    return True


def init_project(root) -> str:
    root = Path(root).resolve()
    _write_mcp_json(root)
    for name in ("CLAUDE.md", "AGENTS.md"):
        _append_steering(root / name)
    hooked = _install_hook(root)
    out = OTHER_SURFACES.format(root=root)
    if hooked:
        out += ("\npre-commit hook installed: every commit prints its blast "
                "radius (remove the cgraphy block from .git/hooks/pre-commit "
                "to opt out).\n")
    return out
