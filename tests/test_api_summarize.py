from cgraphy import summarize
from cgraphy.db import GraphDB


class FakeMessages:
    nid = 0

    def create(self, **kwargs):
        class R:
            content = [type("T", (), {
                "text": '[{"id": %d, "summary": "adds one"}]' % FakeMessages.nid})]
        return R()


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


def test_api_summarize_stores_batch(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    db = GraphDB(tmp_path / ".cgraphy" / "graph.db")
    nid = db.add_node("function", "f", "m.f", file_path="m.py",
                      line_start=1, line_end=2)
    FakeMessages.nid = nid
    monkeypatch.setattr(summarize, "_anthropic_client", lambda: FakeClient())
    n = summarize.api_summarize(db, tmp_path)
    assert n == 1 and db.get_node(nid)["summary"] == "adds one"
    db.close()
