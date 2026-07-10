import json
import subprocess

from cgraphy.enrich_cmd import enrich_repo
from cgraphy.init_cmd import HOOK_MARK, init_project


def _git_init(tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)


def test_init_installs_pre_commit_hook(tmp_path):
    _git_init(tmp_path)
    out = init_project(tmp_path)
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook.is_file() and HOOK_MARK in hook.read_text()
    assert "blast radius" in out
    init_project(tmp_path)  # idempotent
    assert hook.read_text().count(HOOK_MARK) == 1


def test_init_appends_to_existing_hook(tmp_path):
    _git_init(tmp_path)
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho existing\n")
    init_project(tmp_path)
    text = hook.read_text()
    assert "echo existing" in text and HOOK_MARK in text


def test_init_without_git_skips_hook(tmp_path):
    out = init_project(tmp_path)
    assert "blast radius" not in out


def test_steering_v3_is_replacement_style(tmp_path):
    init_project(tmp_path)
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "mcp__cgraphy__cgraphy_search" in text
    assert "Instead of" in text
    assert "NEVER call cgraphy_enrich" in text


def test_enrich_repo_batches_and_persists(tmp_path):
    from cgraphy.indexer import index_repo
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n\n"
                                   "def g(x):\n    return x - 1\n")
    index_repo(tmp_path)

    def fake_runner(blocks, model):
        ids = [int(m) for m in
               __import__("re").findall(r"id=(\d+)", blocks)]
        return [{"id": i, "summary": f"summary for {i}"} for i in ids]

    n = enrich_repo(tmp_path, max_nodes=10, runner=fake_runner)
    assert n >= 2  # f, g (+ file node)
    assert enrich_repo(tmp_path, max_nodes=10, runner=fake_runner) == 0


def test_enrich_stops_when_runner_returns_nothing(tmp_path):
    from cgraphy.indexer import index_repo
    (tmp_path / "m.py").write_text("def f():\n    pass\n")
    index_repo(tmp_path)
    n = enrich_repo(tmp_path, max_nodes=10, runner=lambda b, m: [])
    assert n == 0
