"""Agent patch generation on SWE-bench Lite with the Claude CLI.

Same two arms as eval_agent.py (baseline file tools vs +cgraphy MCP), but
the agent is asked to FIX the issue; we harvest `git diff` as the model
patch. Output is a SWE-bench predictions JSONL per arm, ready for
`swebench.harness.run_evaluation`.

Usage:
  uv run python scripts/eval_patch.py LITE_JSON CLONES_DIR OUT_DIR \
      [--limit N] [--arms baseline,cgraphy] [--model MODEL] repo1 repo2 ...
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from eval_agent import make_query, tokens_of
from eval_swebench import checkout

PROJ = str(Path(__file__).resolve().parent.parent)

PROMPT = """You are fixing a bug in the repository '{repo}'.

GitHub issue:
{issue}

Task: find the root cause and FIX it by editing the source code.
- Make the minimal correct change; do not refactor unrelated code.
- Do not modify tests, docs, or configuration.
- Explore efficiently; edit only what is necessary.
When the fix is complete, reply DONE with a one-line summary."""


def run_claude(cwd, prompt, arm, model, max_turns=40):
    allowed = "Read,Grep,Glob,Edit,Write"
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--model", model, "--max-turns", str(max_turns),
           "--disallowedTools", "Bash,WebSearch,WebFetch,Task",
           "--dangerously-skip-permissions"]
    if arm == "cgraphy":
        mcp = {"mcpServers": {"cgraphy": {
            "command": "uv",
            "args": ["run", "--project", PROJ, "--with", "model2vec",
                     "cgraphy", "serve", "."]}}}
        cmd += ["--mcp-config", json.dumps(mcp), "--strict-mcp-config"]
        allowed += ",mcp__cgraphy"
    cmd += ["--allowedTools", allowed]
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=1200)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    # the CLI exits 1 when max-turns is hit but still emits full result JSON
    try:
        out = json.loads(r.stdout)
        if isinstance(out, dict) and "usage" in out:
            return out
    except ValueError:
        pass
    return {"error": f"exit={r.returncode} out={r.stdout[-200:]} "
                     f"err={r.stderr[-200:]}"}


def harvest_patch(repo: Path) -> str:
    # revert artifacts cgraphy itself may have touched, keep agent edits
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--",
                    ".gitignore"], capture_output=True)
    r = subprocess.run(["git", "-C", str(repo), "diff"],
                       capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lite_json"); ap.add_argument("clones")
    ap.add_argument("out_dir")
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--arms", default="baseline,cgraphy")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = ap.parse_args()

    lite = json.load(open(args.lite_json))
    clones = Path(args.clones)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    insts = [i for i in lite if i["repo"].split("/")[-1] in args.repos]
    insts.sort(key=lambda i: i["repo"])
    if args.limit:
        insts = insts[:args.limit]

    for arm in args.arms.split(","):
        pred_path = out_dir / f"preds_{arm}.jsonl"
        meta_path = out_dir / f"meta_{arm}.jsonl"
        have = set()
        if pred_path.exists():
            for line in pred_path.read_text().splitlines():
                try:
                    have.add(json.loads(line)["instance_id"])
                except ValueError:
                    pass
        for inst in insts:
            if inst["instance_id"] in have:
                continue
            name = inst["repo"].split("/")[-1]
            repo = clones / name
            if not checkout(repo, inst["base_commit"]):
                continue
            shutil.rmtree(repo / ".cgraphy", ignore_errors=True)
            if arm == "cgraphy":
                subprocess.run(
                    ["uv", "run", "--project", PROJ, "--with", "model2vec",
                     "cgraphy", "index", str(repo), "--git-history"],
                    capture_output=True, timeout=600)
            prompt = PROMPT.format(repo=name,
                                   issue=make_query(inst["problem_statement"],
                                                    max_words=400))
            res = run_claude(repo, prompt, arm, args.model)
            patch = harvest_patch(repo)
            with open(pred_path, "a") as f:
                f.write(json.dumps({
                    "instance_id": inst["instance_id"],
                    "model_name_or_path": f"haiku45-{arm}",
                    "model_patch": patch}) + "\n")
            with open(meta_path, "a") as f:
                f.write(json.dumps({
                    "instance_id": inst["instance_id"],
                    "patch_bytes": len(patch),
                    "tokens": tokens_of(res.get("usage", {})),
                    "turns": res.get("num_turns"),
                    "cost_usd": res.get("total_cost_usd"),
                    "error": res.get("error")}) + "\n")
            print(f"{inst['instance_id']} [{arm}] patch={len(patch)}B "
                  f"turns={res.get('num_turns')} "
                  f"cost=${res.get('total_cost_usd')}", flush=True)


if __name__ == "__main__":
    main()
