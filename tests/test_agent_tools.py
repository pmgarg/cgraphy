"""Tests for the edit-loop tools: read, impact, diff_context."""
import subprocess

import pytest

from cgraphy.db import GraphDB
from cgraphy.graphq import estimate_tokens, impact, read_symbol


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core.py").write_text(
        "def parse(x):\n    return x\n\n\ndef run(x):\n    return parse(x)\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text(
        "from src.core import parse\n\ndef test_parse():\n    assert parse(1)\n")
    db = GraphDB(tmp_path / ".cgraphy" / "graph.db")
    core = db.add_node("file", "core.py", "src/core.py", file_path="src/core.py")
    parse = db.add_node("function", "parse", "src.core.parse",
                        file_path="src/core.py", line_start=1, line_end=2,
                        signature="def parse(x):")
    run = db.add_node("function", "run", "src.core.run",
                      file_path="src/core.py", line_start=5, line_end=6)
    tf = db.add_node("file", "test_core.py", "tests/test_core.py",
                     file_path="tests/test_core.py")
    tfn = db.add_node("function", "test_parse", "tests.test_core.test_parse",
                      file_path="tests/test_core.py", line_start=3, line_end=4)
    db.add_edge(core, parse, "contains")
    db.add_edge(run, parse, "calls")
    db.add_edge(tfn, parse, "calls")
    db.add_edge(tf, core, "co_changes", weight=0.9)
    db.set_ranks({parse: 1.0, run: 0.5, tfn: 0.3, core: 0.2, tf: 0.1})
    db.commit()
    yield tmp_path, db
    db.close()


def test_read_symbol_returns_exact_snippet(repo):
    root, db = repo
    out = read_symbol(db, root, "parse")
    assert "def parse(x):" in out and "return x" in out
    assert "src/core.py:1" in out
    assert "def run" not in out            # only the symbol, not the file


def test_read_symbol_respects_budget_and_missing(repo):
    root, db = repo
    assert estimate_tokens(read_symbol(db, root, "parse", token_budget=50)) <= 50
    assert "No node found" in read_symbol(db, root, "nope_xyz")


def test_impact_lists_dependents_tests_and_cochange(repo):
    root, db = repo
    out = impact(db, "parse")
    assert "src.core.run" in out                    # direct dependent
    assert "test_parse" in out                      # affected test
    assert "tests/test_core.py" in out
    assert "co-change" in out.lower() or "co_changes" in out


def test_impact_unknown_symbol_graceful(repo):
    root, db = repo
    assert "No node found" in impact(db, "ghost_fn")


def test_diff_context_maps_changed_lines_to_symbols(tmp_path):
    from cgraphy.diffctx import diff_context
    from cgraphy.indexer import index_repo, db_path
    (tmp_path / "m.py").write_text("def a():\n    return 1\n\ndef b():\n    return 2\n")
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True,
                   env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-q", "-m", "init"], check=True)
    index_repo(tmp_path)
    (tmp_path / "m.py").write_text("def a():\n    return 99\n\ndef b():\n    return 2\n")
    db = GraphDB(db_path(tmp_path))
    out = diff_context(db, tmp_path)
    assert "m.a" in out and "m.b" not in out       # only the touched symbol
    db.close()


def test_diff_context_clean_tree_graceful(tmp_path):
    from cgraphy.diffctx import diff_context
    db = GraphDB(tmp_path / ".cgraphy" / "graph.db")
    assert "No" in diff_context(db, tmp_path)      # no git repo / no diff
    db.close()
