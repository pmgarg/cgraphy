from cgraphy.communities import apply_communities
from cgraphy.db import GraphDB
from cgraphy.graphq import overview


def make_two_clusters(db):
    """Two import-clusters of files: {a,b,c} and {x,y}."""
    ids = {}
    for name in ("a", "b", "c", "x", "y"):
        ids[name] = db.add_node("file", f"{name}.py", f"{name}.py",
                                file_path=f"{name}.py")
    db.add_edge(ids["a"], ids["b"], "imports")
    db.add_edge(ids["b"], ids["c"], "imports")
    db.add_edge(ids["a"], ids["c"], "imports")
    db.add_edge(ids["x"], ids["y"], "imports")
    db.set_ranks({ids["a"]: 1.0, ids["x"]: 0.8})
    return ids


def test_label_propagation_separates_clusters(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    ids = make_two_clusters(db)
    apply_communities(db)
    comm = {n: db.get_node(i)["community"] for n, i in ids.items()}
    assert comm["a"] == comm["b"] == comm["c"]
    assert comm["x"] == comm["y"]
    assert comm["a"] != comm["x"]
    db.close()


def test_symbols_inherit_file_community(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    ids = make_two_clusters(db)
    fn = db.add_node("function", "f", "a.f", file_path="a.py")
    apply_communities(db)
    assert db.get_node(fn)["community"] == db.get_node(ids["a"])["community"]
    db.close()


def test_overview_shows_subsystems(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    make_two_clusters(db)
    apply_communities(db)
    text = overview(db)
    assert "Subsystems" in text
    db.close()
