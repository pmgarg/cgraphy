import pytest

from cgraphy.db import GraphDB
from cgraphy.graphq import context, estimate_tokens, overview, search


@pytest.fixture()
def db(tmp_path):
    d = GraphDB(tmp_path / "g.db")
    f = d.add_node("file", "auth.py", "src/auth.py", file_path="src/auth.py")
    login = d.add_node("function", "login", "src.auth.login",
                       file_path="src/auth.py", line_start=10, line_end=30,
                       signature="def login(user, pw):")
    check = d.add_node("function", "check_token", "src.auth.check_token",
                       file_path="src/auth.py", line_start=32, line_end=40,
                       signature="def check_token(tok):")
    d.update_summary(login, "authenticates a user and mints a JWT", "h1")
    d.update_summary(check, "validates JWT expiry and signature", "h2")
    d.add_edge(f, login, "contains")
    d.add_edge(login, check, "calls")
    d.add_ref(login, "calls", "mystery_helper")
    d.set_ranks({login: 1.0, check: 0.6, f: 0.2})
    d.commit()
    yield d
    d.close()


def test_overview_lists_key_symbols_and_files(db):
    text = overview(db)
    assert "src.auth.login" in text and "auth.py" in text
    assert "authenticates a user" in text
    assert estimate_tokens(text) <= 2000


def test_search_finds_by_summary_words(db):
    text = search(db, "JWT expiry")
    assert "check_token" in text and "src/auth.py:32" in text


def test_context_includes_neighbors_and_unresolved(db):
    text = context(db, "login")
    assert "src.auth.login" in text and "def login(user, pw):" in text
    assert "check_token" in text          # callee appears
    assert "mystery_helper" in text       # unresolved ref listed


def test_context_respects_budget(db):
    text = context(db, "login", token_budget=60)
    assert estimate_tokens(text) <= 60


def test_context_unknown_symbol_is_graceful(db):
    assert "No node found" in context(db, "does_not_exist_xyz")
