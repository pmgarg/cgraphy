from cgraphy.db import GraphDB
from cgraphy.pagerank import apply_pagerank, pagerank


def test_hub_gets_highest_rank():
    nodes = [1, 2, 3, 4]
    edges = [(2, 1, 1.0), (3, 1, 1.0), (4, 1, 1.0), (1, 2, 1.0)]
    r = pagerank(edges, nodes)
    assert r[1] == 1.0
    assert r[1] > r[2] > 0


def test_empty_graph():
    assert pagerank([], []) == {}


def test_apply_pagerank_writes_ranks(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    a = db.add_node("function", "a", "m.a", file_path="m.py")
    b = db.add_node("function", "b", "m.b", file_path="m.py")
    c = db.add_node("function", "c", "m.c", file_path="m.py")
    db.add_edge(b, a, "calls")
    db.add_edge(c, a, "calls")
    apply_pagerank(db)
    assert db.get_node(a)["rank"] == 1.0
    assert 0 < db.get_node(b)["rank"] < 1.0
    db.close()
