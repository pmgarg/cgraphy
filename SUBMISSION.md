# Launch guide: arXiv, PyPI, MCP registries, workshop

Everything below that a machine can do is already done (PDF compiled,
tarball built, dist/ built, server.json written). The steps marked **YOU**
need your identity/accounts and take ~15 minutes each.

## 1. arXiv (first-time author walkthrough)

What arXiv is: a moderated preprint server, not peer review. In-scope,
well-formed papers post within 1–3 business days. Posting gives you a
citable ID and timestamps your work — do this before the workshop.

1. **YOU — create the account**: https://arxiv.org/user/register with your
   email. Use your real name "Prateek Mohan Garg" (it becomes your author
   identity). Add ORCID if you have one (recommended, free: orcid.org).
2. **YOU — endorsement (maybe)**: first-time submitters to cs.SE sometimes
   need an endorsement. After you start a submission arXiv tells you if
   it's required and gives you an endorsement code + link to send to any
   endorsed author (e.g., a colleague/professor who has published in cs).
   If you know no one, arXiv sometimes waives it based on your email
   domain/history — try first.
3. **Submission**: https://arxiv.org/submit → new submission.
   - License: **CC BY 4.0** (recommended) or arXiv's default
     non-exclusive license.
   - Primary category: **cs.SE** (Software Engineering);
     cross-list: **cs.AI** and **cs.IR**.
   - Title: "Which Graph Signals Pay for Their Tokens? cgraphy: A
     Token-Budgeted Code Knowledge Graph as a Portable Context Layer for
     AI Coding Agents".
   - Upload: `paper/arxiv-submission.tar.gz` (already built — contains
     cgraphy.tex + both figure PDFs; arXiv compiles it server-side, and it
     compiles cleanly with tectonic locally, which is stricter).
   - Abstract: paste from the paper (plain text, no LaTeX macros beyond $...$).
   - Author: Prateek Mohan Garg.
4. Preview the arXiv-generated PDF, fix anything, submit. Moderation
   typically completes in 1–3 business days; you'll get arXiv:2607.NNNNN.
5. After it posts: add the arXiv badge/link to the GitHub README.

### 1b. No endorsement yet? Publish NOW on Zenodo (equal citability)

Endorsement can take weeks. Do this today instead of waiting — it does
NOT conflict with posting to arXiv later:

1. **Zenodo** (https://zenodo.org — CERN, free, permanent):
   - Sign up (or log in with GitHub) → "New upload".
   - Upload `paper/cgraphy.pdf`. Type: Preprint. License: CC BY 4.0.
   - Title/abstract/author: copy from the paper. Keywords: code knowledge
     graph, MCP, AI coding agents, SWE-bench.
   - Publish → you get a **DOI** (e.g. 10.5281/zenodo.XXXXXXX)
     immediately. A DOI is a first-class citable identifier — for many
     purposes stronger than an arXiv ID.
   - Bonus: in Zenodo → GitHub integration, flip the switch for
     `pmgarg/cgraphy` and create a GitHub Release `v1.0.0` — the code
     archive gets its own DOI (CITATION.cff in the repo feeds the
     metadata automatically).
2. Optional second mirror: **TechRxiv** (https://www.techrxiv.org, IEEE)
   — classic preprint look, light moderation, no endorsement, also a DOI.
3. Put the DOI badge in the README and cite it as
   "Garg, P. M. (2026). ... Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX".
4. **Keep hunting the arXiv endorsement in parallel** — the highest-yield
   route: email the corresponding authors of papers we cite (RepoGraph,
   LocAgent, CodexGraph — early-career authors usually respond) with your
   endorsement code, one paragraph, and the Zenodo link. When arXiv
   accepts later, both records coexist; arXiv will show as v1 there.
5. **Never** use viXra or any paid "rapid publication journal" — both
   actively damage credibility.

Note: the workshop targets in §4 do NOT require arXiv — peer-reviewed
publication there is the real credibility milestone, and the Zenodo DOI
is fully sufficient to cite in the meantime.

## 2. PyPI

`cgraphy` is **available** on PyPI (verified 2026-07-09). Artifacts are in
`dist/` (wheel + sdist, contents verified incl. the viewer's static files).

1. **YOU — account**: https://pypi.org/account/register/ → verify email →
   enable 2FA (required) → Account settings → API tokens → create a token
   scoped "entire account" (first upload creates the project).
2. **Publish** (from the repo root):
   ```bash
   UV_PUBLISH_TOKEN=pypi-xxxx uv publish
   ```
3. Verify: `uvx cgraphy --version` from any machine.
4. After first publish, replace the account-wide token with a
   project-scoped one.

## 3. MCP registries

- **Official registry** (registry.modelcontextprotocol.io): `server.json`
  is written at the repo root. Install the publisher CLI and push:
  ```bash
  brew install mcp-publisher
  mcp-publisher login github   # auth as pmgarg — proves the io.github.pmgarg namespace
  mcp-publisher publish
  ```
  (Do this AFTER the PyPI publish so the package reference validates.)
- **Community directories** (free listings, drive most discovery):
  - PulseMCP: https://www.pulsemcp.com/submit (Auto-ingests from Official Registry)
  - mcp.so: submit via their GitHub issue template (Submitted: https://github.com/chatmcp/mcpso/issues/3126)
  - Smithery: https://smithery.ai — connect the GitHub repo (Ready: smithery.yaml added)
- **Awesome lists**: PR to `punkpeye/awesome-mcp-servers` under
  "Code Analysis" with a one-liner + link.

## 4. Workshop targets (the peer-review step)

In order of fit:
1. **LLM4Code** (ICSE workshop) — perfect topical fit; 4–8 page papers;
   deadlines typically Oct–Nov for the spring conference. Check
   llm4code.github.io for the 2027 CFP.
2. **FORGE** (AI Foundation Models & Software Engineering) — same
   community, slightly broader scope.
3. **ASE / FSE tool demonstrations track** — cgraphy qualifies as a tool
   demo (6 pages + video); demo tracks value working artifacts, which is
   our strength.

Strategy: post to arXiv now (priority + citable), then adapt to the
workshop page limit when the CFP opens. Mention the public repo,
reproducible benchmarks, and the agent-in-the-loop experiment prominently
— artifact availability is a review criterion at all three venues.

## 5. Already done (no action needed)

- Paper compiles: `paper/cgraphy.pdf` (tectonic, no errors).
- arXiv source bundle: `paper/arxiv-submission.tar.gz`.
- PyPI artifacts: `dist/cgraphy-0.1.0-py3-none-any.whl` + sdist.
- Registry manifest: `server.json`.
- Benchmarks: `scripts/eval_localization.py`, `scripts/eval_swebench.py`,
  `scripts/eval_agent.py` (agent-in-the-loop, resumable JSONL).
