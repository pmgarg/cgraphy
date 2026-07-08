import pytest

from cgraphy.db import GraphDB


@pytest.fixture()
def db(tmp_path):
    d = GraphDB(tmp_path / "graph.db")
    yield d
    d.close()


def test_add_and_get_node(db):
    nid = db.add_node("function", "foo", "pkg.mod.foo", language="python",
                      file_path="pkg/mod.py", line_start=1, line_end=3,
                      signature="def foo(x)")
    row = db.get_node(nid)
    assert row["qualified_name"] == "pkg.mod.foo" and row["kind"] == "function"


def test_node_by_ref_matches_qname_name_and_path(db):
    nid = db.add_node("function", "foo", "pkg.mod.foo", file_path="pkg/mod.py")
    assert db.node_by_ref("pkg.mod.foo")["id"] == nid
    assert db.node_by_ref("foo")["id"] == nid
    fid = db.add_node("file", "mod.py", "pkg/mod.py", file_path="pkg/mod.py")
    assert db.node_by_ref("pkg/mod.py")["id"] == fid


def test_clear_file_removes_nodes_edges_and_fts(db):
    a = db.add_node("function", "a", "m.a", file_path="m.py")
    b = db.add_node("function", "b", "n.b", file_path="n.py")
    db.add_edge(a, b, "calls")
    db.clear_file("m.py")
    assert db.get_node(a) is None
    assert db.get_node(b) is not None
    assert db.all_edges() == []
    assert db.search_fts("a", 10) == []


def test_search_prefers_higher_rank(db):
    lo = db.add_node("function", "parse", "x.parse", file_path="x.py")
    hi = db.add_node("function", "parse", "y.parse", file_path="y.py")
    db.set_ranks({hi: 1.0, lo: 0.0})
    rows = db.search_fts("parse", 10)
    assert rows[0]["id"] == hi


def test_summary_roundtrip_and_unsummarized(db):
    nid = db.add_node("function", "f", "m.f", file_path="m.py")
    assert [r["id"] for r in db.unsummarized(10)] == [nid]
    db.update_summary(nid, "does f things", "hash1")
    assert db.unsummarized(10) == []
    assert db.summaries_for_file("m.py") == {"m.f": ("does f things", "hash1")}
    assert db.search_fts("things", 10)[0]["id"] == nid


def test_file_hash_tracking(db):
    db.set_file("m.py", "abc", 123.0)
    assert db.get_file("m.py") == ("abc", 123.0)
    assert db.indexed_paths() == {"m.py"}
    db.delete_file("m.py")
    assert db.get_file("m.py") is None
