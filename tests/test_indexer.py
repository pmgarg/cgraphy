import hashlib
import time

from cgraphy.db import GraphDB
from cgraphy.indexer import db_path, index_repo, module_qname


def make_repo(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        "def alpha(x):\n    return beta(x)\n")
    (tmp_path / "pkg" / "b.py").write_text(
        "from pkg.a import alpha\n\ndef beta(x):\n    return x\n")
    (tmp_path / ".gitignore").write_text("dist/\n")
    return tmp_path


def test_module_qname():
    assert module_qname("pkg/a.py") == "pkg.a"
    assert module_qname("src/x/y.rs") == "src.x.y"


def test_index_creates_nodes_edges_and_resolves_calls(tmp_path):
    repo = make_repo(tmp_path)
    stats = index_repo(repo)
    assert stats["files_indexed"] == 3  # a.py b.py .gitignore
    db = GraphDB(db_path(repo))
    alpha = db.node_by_ref("pkg.a.alpha")
    beta = db.node_by_ref("pkg.b.beta")
    kinds = {(e["source_id"], e["target_id"], e["kind"]) for e in db.all_edges()}
    assert (alpha["id"], beta["id"], "calls") in kinds
    file_a = db.node_by_ref("pkg/a.py")
    assert (file_a["id"], alpha["id"], "contains") in kinds
    db.close()


def test_incremental_skips_unchanged_and_updates_changed(tmp_path):
    repo = make_repo(tmp_path)
    index_repo(repo)
    stats2 = index_repo(repo)
    assert stats2["files_indexed"] == 0
    time.sleep(0.01)
    (repo / "pkg" / "a.py").write_text("def alpha2(x):\n    return x\n")
    stats3 = index_repo(repo)
    assert stats3["files_indexed"] == 1
    db = GraphDB(db_path(repo))
    assert db.node_by_ref("pkg.a.alpha2") is not None
    assert db.node_by_ref("pkg.a.alpha") is None
    db.close()


def test_deleted_file_purged(tmp_path):
    repo = make_repo(tmp_path)
    index_repo(repo)
    (repo / "pkg" / "b.py").unlink()
    index_repo(repo)
    db = GraphDB(db_path(repo))
    assert db.node_by_ref("pkg.b.beta") is None
    assert "pkg/b.py" not in db.indexed_paths()
    db.close()


def test_summary_survives_reindex_when_code_unchanged(tmp_path):
    repo = make_repo(tmp_path)
    index_repo(repo)
    db = GraphDB(db_path(repo))
    node = db.node_by_ref("pkg.a.alpha")
    snippet = "def alpha(x):\n    return beta(x)\n"
    h = hashlib.sha256(snippet.encode()).hexdigest()
    db.update_summary(node["id"], "adds one", h)
    db.close()
    time.sleep(0.01)
    (repo / "pkg" / "a.py").write_text(
        "def alpha(x):\n    return beta(x)\n\ndef gamma():\n    pass\n")
    index_repo(repo)
    db = GraphDB(db_path(repo))
    assert db.node_by_ref("pkg.a.alpha")["summary"] == "adds one"
    assert db.node_by_ref("pkg.a.gamma")["summary"] == ""
    db.close()


def test_gitignore_gets_cgraphy_line(tmp_path):
    repo = make_repo(tmp_path)
    index_repo(repo)
    assert ".cgraphy/" in (repo / ".gitignore").read_text()
