import pytest

from cgraphy.db import GraphDB
from cgraphy.summarize import enrich_batch, store_summaries


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    db = GraphDB(tmp_path / ".cgraphy" / "graph.db")
    nid = db.add_node("function", "f", "m.f", file_path="m.py",
                      line_start=1, line_end=2, signature="def f(x):")
    db.set_ranks({nid: 1.0})
    db.commit()
    yield tmp_path, db, nid
    db.close()


def test_enrich_returns_snippet_and_instructions(repo):
    root, db, nid = repo
    text = enrich_batch(db, root)
    assert f"id={nid}" in text and "return x + 1" in text
    assert "cgraphy_store_summaries" in text


def test_store_then_enrich_empty(repo):
    root, db, nid = repo
    out = store_summaries(db, root, [{"id": nid, "summary": "adds one to x"}])
    assert "Stored 1" in out
    assert db.get_node(nid)["summary"] == "adds one to x"
    assert db.get_node(nid)["summary_hash"] != ""
    assert "summarized" in enrich_batch(db, root)


def test_store_bad_id_is_graceful(repo):
    root, db, _ = repo
    out = store_summaries(db, root, [{"id": 99999, "summary": "x"}])
    assert "Stored 0" in out
