from cgraphy.db import GraphDB
from cgraphy.viewer import graph_json


def test_graph_json_shape(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    f = db.add_node("file", "a.py", "a.py", file_path="a.py")
    fn = db.add_node("function", "f", "a.f", file_path="a.py", line_start=1)
    db.add_edge(f, fn, "contains")
    db.set_ranks({fn: 1.0, f: 0.5})
    g = graph_json(db)
    ids = {n["data"]["id"] for n in g["nodes"]}
    assert ids == {str(f), str(fn)}
    assert g["edges"][0]["data"] == {"source": str(f), "target": str(fn),
                                     "kind": "contains"}
    db.close()
