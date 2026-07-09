from cgraphy.db import GraphDB
from cgraphy.graphq import context
from cgraphy.indexer import db_path, index_repo


def test_csv_and_sql_files_get_schema_summaries(tmp_path):
    (tmp_path / "users.csv").write_text("id,email,signup_date\n1,a@b.c,2026\n")
    (tmp_path / "schema.sql").write_text(
        "CREATE TABLE users (id INT);\nCREATE TABLE orders (id INT);\n")
    index_repo(tmp_path)
    db = GraphDB(db_path(tmp_path))
    csv_node = db.node_by_ref("users.csv")
    assert "email" in csv_node["summary"] and "signup_date" in csv_node["summary"]
    sql_node = db.node_by_ref("schema.sql")
    assert "users" in sql_node["summary"] and "orders" in sql_node["summary"]
    # schema words are searchable
    assert db.search_fts("signup_date", 5)[0]["id"] == csv_node["id"]
    db.close()


def test_usage_boost_reorders_equal_neighbors(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    hub = db.add_node("function", "hub", "m.hub", file_path="m.py")
    cold = db.add_node("function", "cold", "m.cold", file_path="m.py")
    hot = db.add_node("function", "hot", "m.hot", file_path="m.py")
    db.add_edge(hub, cold, "calls")
    db.add_edge(hub, hot, "calls")
    db.set_ranks({cold: 0.5, hot: 0.5})
    for _ in range(5):
        db.log_usage(hot)
    out = context(db, "hub")
    assert out.index("m.hot") < out.index("m.cold")
    db.close()


def test_context_logs_usage_of_target(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    n = db.add_node("function", "f", "m.f", file_path="m.py")
    context(db, "f")
    assert db.usage_counts()[n] == 1
    db.close()
