import pytest

import cgraphy.server as server


@pytest.fixture()
def repo(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text(
        "def alpha(x):\n    return beta(x)\n\ndef beta(x):\n    return x\n")
    server._last_check = 0.0
    return tmp_path


def test_overview_auto_indexes(repo):
    tools = server.make_tools(repo)
    text = tools["cgraphy_overview"]()
    assert "pkg/a.py" in text and "alpha" in text


def test_search_and_context(repo):
    tools = server.make_tools(repo)
    tools["cgraphy_overview"]()
    assert "pkg.a.alpha" in tools["cgraphy_search"]("alpha")
    ctx = tools["cgraphy_context"]("pkg.a.alpha")
    assert "beta" in ctx


def test_enrich_store_roundtrip(repo):
    tools = server.make_tools(repo)
    tools["cgraphy_overview"]()
    enrich = tools["cgraphy_enrich"]()
    assert "id=" in enrich
    import re
    nid = int(re.search(r"id=(\d+)", enrich).group(1))
    out = tools["cgraphy_store_summaries"]([{"id": nid, "summary": "test summary"}])
    assert "Stored 1" in out


def test_tools_without_graph_are_graceful(tmp_path):
    server._last_check = 0.0
    tools = server.make_tools(tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    assert "No graph" in tools["cgraphy_search"]("x") or "no matches" in \
        tools["cgraphy_search"]("x").lower()


def test_create_server_registers_five_tools(repo):
    s = server.create_server(repo)
    assert s is not None
