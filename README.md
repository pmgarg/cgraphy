# cgraphy

**A code knowledge graph for AI coding agents, served over MCP.**

cgraphy indexes any codebase into a knowledge graph — functions, classes and
files as nodes; calls, imports, inheritance and git co-change history as
edges — and serves compact, token-budgeted slices of it to AI assistants
through the [Model Context Protocol](https://modelcontextprotocol.io). Instead
of re-reading dozens of files to orient itself on every prompt, an agent asks
the graph and gets the relevant subgraph in a couple of thousand tokens.

- **Any language.** Full-fidelity extraction (calls, imports, inheritance) for
  Python, TypeScript/JavaScript, Java, Go, C, C++ and Rust; generic
  definition-level extraction for 20+ more via tree-sitter; config and docs
  files participate through summaries.
- **Importance-ranked.** PageRank over the code graph puts load-bearing
  symbols first in every answer.
- **Token-budgeted.** `cgraphy_context` expands the graph greedily around a
  symbol and stops exactly at your token budget — cost scales with the
  question, not the repo.
- **Git-aware.** `--git-history` mines commit history for files that change
  together (logical coupling), an edge type static analysis can't see.
- **No API key.** Semantic summaries are written by the host agent itself
  through the enrich loop; summaries survive re-indexing via content hashing.
- **Zero infrastructure.** One SQLite file in `.cgraphy/`. No services, no
  daemons, no vector database.

## Install

```bash
pip install cgraphy        # or: uv tool install cgraphy
```

## Quick start

```bash
cd your-repo
cgraphy index . --git-history
```

Then register the MCP server with your assistant:

**Claude Code**

```bash
claude mcp add cgraphy -- uvx cgraphy serve /path/to/repo
```

**Codex CLI** (`~/.codex/config.toml`)

```toml
[mcp_servers.cgraphy]
command = "uvx"
args = ["cgraphy", "serve", "/path/to/repo"]
```

**Gemini CLI** (`~/.gemini/settings.json`) / **Cursor** (`.cursor/mcp.json`)

```json
{"mcpServers": {"cgraphy": {"command": "uvx",
                            "args": ["cgraphy", "serve", "/path/to/repo"]}}}
```

## The five tools

| Tool | Returns | The agent uses it… |
| --- | --- | --- |
| `cgraphy_overview` | Repo map: key symbols by importance + all files, ~1–2K tokens | first, instead of reading files to orient |
| `cgraphy_search` | Ranked symbol matches with `file:line` and summaries | before grep / directory listing |
| `cgraphy_context` | Subgraph around a symbol (callers, callees, imports, co-changes) within a token budget | instead of reading whole files |
| `cgraphy_enrich` | Batch of symbols that still need one-line summaries | when asked to "enrich the graph" |
| `cgraphy_store_summaries` | Confirmation + remaining count | to save the summaries it wrote |

The graph self-heals: tools detect stale files and re-index incrementally
(changed files only) before answering.

## Enriching the graph

Structure is extracted automatically; *meaning* comes from summaries. Tell
your agent once:

> enrich the cgraphy graph

It will loop `cgraphy_enrich` → `cgraphy_store_summaries` until every symbol
has a one-line semantic summary. Summaries are keyed to a hash of each
symbol's source, so editing one function invalidates only that summary.

For CI, `cgraphy index --summarize` pre-bakes summaries with your own
Anthropic API key (`pip install cgraphy[summarize]`, `ANTHROPIC_API_KEY` set).

## Viewer

```bash
cgraphy view .        # http://localhost:8787
```

A dependency-free local page (bundled Cytoscape.js): search, color by kind,
click for details, double-click to expand neighbors; co-change edges shown
dashed.

## Measuring the savings

```bash
python scripts/benchmark.py /path/to/repo "your question"
```

Prints the tokens an agent spends orienting via cgraphy (overview + search +
context) versus reading every code file, and the reduction factor.

## How it works

1. `cgraphy index` walks the repo (respecting `.gitignore` +
   `.cgraphyignore`), parses each file with tree-sitter, and stores nodes and
   edges in `.cgraphy/graph.db` (SQLite + FTS5). Re-indexing is incremental by
   content hash.
2. A resolver links cross-file references (calls, imports, inheritance) by
   qualified name, best-effort; unresolved names are kept, never dropped.
3. PageRank runs over the edge graph; every query surfaces important symbols
   first. Search blends FTS5 relevance with rank.
4. `cgraphy serve` exposes the five MCP tools over stdio.
5. Optional: `--git-history` adds weighted co-change edges mined from
   `git log`.

Design details: [docs/superpowers/specs/2026-07-08-cgraphy-design.md](docs/superpowers/specs/2026-07-08-cgraphy-design.md)

## License

MIT
