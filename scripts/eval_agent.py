"""Agent-in-the-loop localization on SWE-bench Lite with the Claude CLI.

Two arms, identical prompts, identical model and turn budget:
  baseline : Read/Grep/Glob file tools only
  cgraphy  : same file tools + the cgraphy MCP server (8 graph tools)

For each instance we check out the pre-fix snapshot, ask the agent to name
the files that must be modified, and score against the gold patch. We also
record what the run cost: tokens, turns, wall time, dollars.

Results append to a JSONL file so interrupted sweeps resume cleanly.

Usage:
  uv run python scripts/eval_agent.py LITE_JSON CLONES_DIR OUT_JSONL \
      [--limit N] [--arms baseline,cgraphy] [--model MODEL] repo1 repo2 ...
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from eval_swebench import checkout, patch_files

PROJ = str(Path(__file__).resolve().parent.parent)

PROMPT = """You are localizing a bug in the repository '{repo}'.

GitHub issue:
{issue}

Task: identify the source files that must be MODIFIED to fix this issue.
Explore efficiently - do not read more than you need.
When confident, reply with ONLY a JSON array of repo-relative file paths
(most likely first, at most 10). No other text in the final message."""


def make_query(problem, max_words=250):
    text = re.sub(r"```.*?```", " [code] ", problem, flags=re.S)
    return " ".join(text.split()[:max_words])


def write_steering(repo):
    """The as-deployed config: the CLAUDE.md block `cgraphy init` installs."""
    from cgraphy.init_cmd import STEERING_BLOCK
    (Path(repo) / "CLAUDE.md").write_text(STEERING_BLOCK.lstrip("\n"))


def run_claude(cwd, prompt, arm, model, max_turns=30):
    allowed = "Read,Grep,Glob"
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--model", model, "--max-turns", str(max_turns),
           "--disallowedTools", "Bash,Write,Edit,WebSearch,WebFetch,Task"]
    if arm in ("cgraphy", "steered"):
        mcp = {"mcpServers": {"cgraphy": {
            "command": "uv",
            "args": ["run", "--project", PROJ, "--with", "model2vec",
                     "cgraphy", "serve", "."]}}}
        cmd += ["--mcp-config", json.dumps(mcp), "--strict-mcp-config"]
        allowed += ",mcp__cgraphy"
    cmd += ["--allowedTools", allowed]
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=600)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    # the CLI exits 1 when max-turns is hit but still emits full result JSON
    try:
        out = json.loads(r.stdout)
        if isinstance(out, dict) and "usage" in out:
            return out
    except ValueError:
        pass
    return {"error": f"exit={r.returncode} out={r.stdout[-300:]} "
                     f"err={r.stderr[-300:]}"}


def extract_files(text):
    for m in reversed(re.findall(r"\[[^\[\]]*\]", text or "", re.S)):
        try:
            arr = json.loads(m)
            if isinstance(arr, list) and all(isinstance(x, str) for x in arr):
                return [x.strip().lstrip("./") for x in arr][:10]
        except ValueError:
            continue
    return []


def tokens_of(usage):
    return sum(usage.get(k, 0) for k in
               ("input_tokens", "output_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lite_json"); ap.add_argument("clones")
    ap.add_argument("out_jsonl")
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--arms", default="baseline,cgraphy")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = ap.parse_args()

    lite = json.load(open(args.lite_json))
    clones = Path(args.clones)
    out = Path(args.out_jsonl)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                rec = json.loads(line)
                if not rec.get("error"):     # errored runs are retried
                    done.add((rec["instance_id"], rec["arm"]))
            except ValueError:
                pass

    insts = [i for i in lite if i["repo"].split("/")[-1] in args.repos]
    insts.sort(key=lambda i: i["repo"])          # group by repo for checkouts
    if args.limit:
        insts = insts[:args.limit]
    arms = args.arms.split(",")

    for inst in insts:
        name = inst["repo"].split("/")[-1]
        repo = clones / name
        gold = set(patch_files(inst["patch"]))
        if not gold:
            continue
        for arm in arms:
            key = (inst["instance_id"], arm)
            if key in done:
                continue
            if not checkout(repo, inst["base_commit"]):
                continue
            shutil.rmtree(repo / ".cgraphy", ignore_errors=True)
            if arm in ("cgraphy", "steered"):  # pre-build graph
                subprocess.run(
                    ["uv", "run", "--project", PROJ, "--with", "model2vec",
                     "cgraphy", "index", str(repo), "--git-history"],
                    capture_output=True, timeout=600)
            if arm == "steered":
                write_steering(repo)
            prompt = PROMPT.format(repo=name,
                                   issue=make_query(inst["problem_statement"]))
            res = run_claude(repo, prompt, arm, args.model)
            if not res.get("error") and tokens_of(res.get("usage", {})) == 0:
                res["error"] = "usage_limit: " + str(res.get("result"))[:80]
                limit_strikes = getattr(main, "_strikes", 0) + 1
                main._strikes = limit_strikes
                if limit_strikes >= 3:
                    print("usage limit exhausted — stopping sweep (resume "
                          "retries these records)", flush=True)
                    rec = {"instance_id": inst["instance_id"], "arm": arm,
                           "error": res["error"]}
                    with open(out, "a") as f:
                        f.write(json.dumps(rec) + "\n")
                    sys.exit(3)
            else:
                main._strikes = 0
            files = extract_files(res.get("result", ""))
            first = next((i for i, f in enumerate(files) if f in gold), None)
            rec = {
                "instance_id": inst["instance_id"], "arm": arm,
                "gold": sorted(gold), "predicted": files,
                "first_hit": first,
                "hit5": first is not None and first < 5,
                "hit10": first is not None and first < 10,
                "tokens": tokens_of(res.get("usage", {})),
                "turns": res.get("num_turns"),
                "cost_usd": res.get("total_cost_usd"),
                "duration_ms": res.get("duration_ms"),
                "subtype": res.get("subtype"),
                "error": res.get("error"),
            }
            with open(out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"{inst['instance_id']} [{arm}] hit10={rec['hit10']} "
                  f"turns={rec['turns']} tokens={rec['tokens']} "
                  f"cost=${rec['cost_usd']}", flush=True)

    # summary
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    print("\n=== summary ===")
    for arm in arms:
        rs = [r for r in recs if r["arm"] == arm and not r.get("error")]
        if not rs:
            continue
        n = len(rs)
        mrr = sum(1.0 / (r["first_hit"] + 1) for r in rs
                  if r["first_hit"] is not None) / n
        print(f"{arm:<9} n={n} hit@5={sum(r['hit5'] for r in rs)/n:.3f} "
              f"hit@10={sum(r['hit10'] for r in rs)/n:.3f} mrr={mrr:.3f} "
              f"tokens={sum(r['tokens'] for r in rs)/n:,.0f} "
              f"turns={sum(r['turns'] or 0 for r in rs)/n:.1f} "
              f"cost=${sum(r['cost_usd'] or 0 for r in rs)/n:.3f}")


if __name__ == "__main__":
    main()
