# cgraphy – Code Knowledge Graph MCP Server

[![PyPI version](https://img.shields.io/pypi/v/cgraphy.svg)](https://pypi.org/project/cgraphy/)
[![Python versions](https://img.shields.io/pypi/pyversions/cgraphy.svg)](https://pypi.org/project/cgraphy/)
[![License](https://img.shields.io/pypi/l/cgraphy.svg)](https://github.com/pmgarg/cgraphy/blob/master/LICENSE)

**cgraphy** is a Python code knowledge graph and Model Context Protocol (MCP) server for AI coding agents such as Claude Code, Codex CLI, Cursor, and Gemini CLI.

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
- **Proven end-to-end.** In 400+ controlled agent runs on SWE-bench Lite,
  the deployed configuration resolved **14 vs 8** of 57 real GitHub issues
  (official Docker harness). Indexes kubernetes (26K files, 219K nodes) in
  **49s**, keeps it fresh in **1.6s** cycles, answers queries in 1–152ms.
  All benchmarks and predictions are in this repo ([Research paper and benchmarks](https://github.com/pmgarg/cgraphy/tree/master/paper)).

## Install

```bash
pip install cgraphy        # or: uv tool install cgraphy
```

## Quick start

```bash
cd your-repo
cgraphy init          # one command: MCP config + agent steering + index
```

`cgraphy init` does three things:

1. Writes a project-scoped `.mcp.json` — picked up automatically by **Claude
   Code** in all its forms: CLI, VSCode extension, and the desktop app.
2. Appends a steering block to `CLAUDE.md` and `AGENTS.md` telling agents to
   consult the graph (`cgraphy_overview` → `cgraphy_search` →
   `cgraphy_context`) *before* reading files — this is what makes the graph
   actually replace bulk file reading. (Agents can't be forced, only steered:
   instruction files + persuasive tool descriptions + the tools being
   genuinely faster is the mechanism, and it works.)
3. Builds the index with git co-change history.

Or register the MCP server manually with your assistant:

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

## The eight tools

Reading / orientation:

| Tool | Returns | The agent uses it… |
| --- | --- | --- |
| `cgraphy_overview` | Repo map: subsystems, key symbols by importance, all files | first, instead of reading files to orient |
| `cgraphy_search` | Ranked matches with `file:line` and summaries (hybrid lexical+semantic when the `[semantic]` extra is installed) | before grep / directory listing |
| `cgraphy_context` | Subgraph around a symbol (callers, callees, imports, co-changes) within a token budget | instead of reading whole files |
| `cgraphy_read` | Just one symbol's source, line-numbered, budgeted | instead of reading the whole file |

Editing / reviewing — the tools that make the graph part of the change loop:

| Tool | Returns | The agent uses it… |
| --- | --- | --- |
| `cgraphy_impact` | Blast radius: direct + transitive dependents, affected tests, historically co-changed files | before modifying shared code |
| `cgraphy_diff_context` | The working git diff mapped to touched symbols, their users, and covering tests | before committing / when resuming work |

Enrichment:

| Tool | Returns | The agent uses it… |
| --- | --- | --- |
| `cgraphy_enrich` | Batch of symbols that still need one-line summaries | when asked to "enrich the graph" |
| `cgraphy_store_summaries` | Confirmation + remaining count | to save the summaries it wrote |

Retrieval is usage-aware: symbols an agent repeatedly asks about get a small,
capped boost in future context expansion (telemetry stays in the local
SQLite file; nothing leaves your machine).

### Semantic search (optional)

```bash
pip install "cgraphy[semantic]"
```

Adds tiny static embeddings (model2vec, CPU-only, no torch) fused with FTS5
by reciprocal-rank fusion — closes the vocabulary gap between issue-style
prose ("login broken") and code identifiers (`validate_jwt`).

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

## Localization benchmark (research harness)

```bash
python scripts/eval_localization.py /path/to/repo 50
```

Mines fix-like commits from the repo's history (subject = query, touched
files = ground truth, co-change mining excludes evaluated commits), then
scores an ablation ladder — FTS-only, +PageRank, +graph expansion, ±co-change
edges — on hit@5/hit@10/MRR and token cost. No LLM calls, no human grading,
fully reproducible. Results and a paper draft live in [paper/](paper/).

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

Design details: [docs/superpowers/specs/2026-07-08-cgraphy-design.md](https://github.com/pmgarg/cgraphy/blob/master/docs/superpowers/specs/2026-07-08-cgraphy-design.md)

## License

MIT

mcp-name: io.github.pmgarg/cgraphy
