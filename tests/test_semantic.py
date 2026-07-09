"""Semantic layer tests with a fake embedder (no model download in CI)."""
import pytest

from cgraphy import semantic
from cgraphy.db import GraphDB


class FakeModel:
    """Maps auth-flavored text to [1,0], everything else to [0,1]."""

    def encode(self, texts):
        return [[1.0, 0.0] if ("auth" in t.lower() or "login" in t.lower())
                else [0.0, 1.0] for t in texts]


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic, "_get_model", lambda: FakeModel())
    d = GraphDB(tmp_path / "g.db")
    yield d
    d.close()


def test_embed_missing_and_incremental(db):
    a = db.add_node("function", "handler", "m.handler", file_path="m.py")
    db.update_summary(a, "validates authentication tokens", "h")
    assert semantic.embed_missing(db) == 1
    assert semantic.embed_missing(db) == 0  # nothing new


def test_hybrid_finds_semantic_match_fts_misses(db):
    a = db.add_node("function", "handler", "m.handler", file_path="m.py")
    db.update_summary(a, "validates authentication tokens", "h")
    b = db.add_node("function", "format_date", "m.format_date", file_path="m.py")
    semantic.embed_missing(db)
    # FTS5 has no stemming: query 'auth' matches neither summary word
    assert db.search_fts("auth", 10) == []
    rows = semantic.hybrid_search(db, "auth login")
    assert rows and rows[0]["id"] == a


def test_unavailable_model_degrades_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic, "_get_model", lambda: None)
    d = GraphDB(tmp_path / "g.db")
    d.add_node("function", "f", "m.f", file_path="m.py")
    assert semantic.available() is False
    assert semantic.embed_missing(d) == 0
    assert semantic.semantic_ranked(d, "x") == []
    d.close()
