import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes(
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  qualified_name TEXT NOT NULL,
  language TEXT,
  file_path TEXT,
  line_start INTEGER,
  line_end INTEGER,
  signature TEXT DEFAULT '',
  summary TEXT DEFAULT '',
  summary_hash TEXT DEFAULT '',
  parse_error INTEGER DEFAULT 0,
  rank REAL DEFAULT 0.0,
  community INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_nodes_qname ON nodes(qualified_name);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
CREATE TABLE IF NOT EXISTS edges(
  source_id INTEGER NOT NULL,
  target_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  weight REAL DEFAULT 1.0,
  UNIQUE(source_id, target_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(target_id);
CREATE TABLE IF NOT EXISTS refs(
  source_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  target_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refs_src ON refs(source_id);
CREATE TABLE IF NOT EXISTS files(
  path TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL,
  last_indexed REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS usage(
  node_id INTEGER PRIMARY KEY,
  cnt INTEGER DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(
  name, qualified_name, summary
);
"""


def _fts_query(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", text)
    return " OR ".join(f'"{t}"' for t in tokens) if tokens else '""'


class GraphDB:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        try:  # migrate graphs built before the community column existed
            self.conn.execute(
                "ALTER TABLE nodes ADD COLUMN community INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

    def close(self):
        self.conn.commit()
        self.conn.close()

    def commit(self):
        self.conn.commit()

    # --- nodes ---
    def add_node(self, kind, name, qualified_name, language=None, file_path=None,
                 line_start=None, line_end=None, signature="", parse_error=0) -> int:
        cur = self.conn.execute(
            "INSERT INTO nodes(kind,name,qualified_name,language,file_path,"
            "line_start,line_end,signature,parse_error) VALUES(?,?,?,?,?,?,?,?,?)",
            (kind, name, qualified_name, language, file_path,
             line_start, line_end, signature, parse_error))
        nid = cur.lastrowid
        self.conn.execute(
            "INSERT INTO node_fts(rowid,name,qualified_name,summary) VALUES(?,?,?,?)",
            (nid, name, qualified_name, ""))
        return nid

    def get_node(self, node_id):
        return self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()

    def nodes_for_file(self, path):
        return self.conn.execute(
            "SELECT * FROM nodes WHERE file_path=?", (path,)).fetchall()

    def node_by_ref(self, ref):
        for sql, arg in (
            ("SELECT * FROM nodes WHERE qualified_name=? ORDER BY rank DESC", ref),
            ("SELECT * FROM nodes WHERE file_path=? AND kind='file'", ref),
            ("SELECT * FROM nodes WHERE name=? ORDER BY rank DESC", ref),
        ):
            row = self.conn.execute(sql, (arg,)).fetchone()
            if row:
                return row
        return None

    # --- edges / refs ---
    def add_edge(self, source_id, target_id, kind, weight=1.0):
        self.conn.execute(
            "INSERT INTO edges(source_id,target_id,kind,weight) VALUES(?,?,?,?) "
            "ON CONFLICT(source_id,target_id,kind) DO UPDATE SET weight=excluded.weight",
            (source_id, target_id, kind, weight))

    def add_ref(self, source_id, kind, target_name):
        self.conn.execute(
            "INSERT INTO refs(source_id,kind,target_name) VALUES(?,?,?)",
            (source_id, kind, target_name))

    def refs_from(self, node_id):
        return self.conn.execute(
            "SELECT * FROM refs WHERE source_id=?", (node_id,)).fetchall()

    def all_refs(self):
        return self.conn.execute("SELECT * FROM refs").fetchall()

    def all_edges(self):
        return self.conn.execute("SELECT * FROM edges").fetchall()

    def all_node_ids(self):
        return [r["id"] for r in self.conn.execute("SELECT id FROM nodes")]

    def delete_edges_of_kinds(self, kinds):
        q = ",".join("?" * len(kinds))
        self.conn.execute(f"DELETE FROM edges WHERE kind IN ({q})", list(kinds))

    def neighbors(self, node_id):
        out = []
        for r in self.conn.execute(
                "SELECT e.kind AS ekind, e.weight AS w, n.* FROM edges e "
                "JOIN nodes n ON n.id=e.target_id WHERE e.source_id=?", (node_id,)):
            out.append(("out", r["ekind"], r["w"], r))
        for r in self.conn.execute(
                "SELECT e.kind AS ekind, e.weight AS w, n.* FROM edges e "
                "JOIN nodes n ON n.id=e.source_id WHERE e.target_id=?", (node_id,)):
            out.append(("in", r["ekind"], r["w"], r))
        return out

    # --- files ---
    def set_file(self, path, content_hash, last_indexed):
        self.conn.execute(
            "INSERT INTO files(path,content_hash,last_indexed) VALUES(?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET content_hash=excluded.content_hash,"
            "last_indexed=excluded.last_indexed", (path, content_hash, last_indexed))

    def get_file(self, path):
        row = self.conn.execute(
            "SELECT content_hash,last_indexed FROM files WHERE path=?", (path,)).fetchone()
        return (row[0], row[1]) if row else None

    def indexed_paths(self):
        return {r[0] for r in self.conn.execute("SELECT path FROM files")}

    def delete_file(self, path):
        self.conn.execute("DELETE FROM files WHERE path=?", (path,))

    def clear_file(self, path):
        ids = [r["id"] for r in self.nodes_for_file(path)]
        if not ids:
            return
        q = ",".join("?" * len(ids))
        self.conn.execute(f"DELETE FROM node_fts WHERE rowid IN ({q})", ids)
        self.conn.execute(f"DELETE FROM edges WHERE source_id IN ({q}) "
                          f"OR target_id IN ({q})", ids + ids)
        self.conn.execute(f"DELETE FROM refs WHERE source_id IN ({q})", ids)
        self.conn.execute(f"DELETE FROM nodes WHERE id IN ({q})", ids)

    # --- search / summaries / ranks ---
    def search_fts(self, query, limit):
        return self.conn.execute(
            "SELECT n.*, bm25(node_fts) AS score FROM node_fts "
            "JOIN nodes n ON n.id=node_fts.rowid WHERE node_fts MATCH ? "
            "ORDER BY bm25(node_fts) - 5.0*n.rank LIMIT ?",
            (_fts_query(query), limit)).fetchall()

    def update_summary(self, node_id, summary, summary_hash):
        self.conn.execute("UPDATE nodes SET summary=?, summary_hash=? WHERE id=?",
                          (summary, summary_hash, node_id))
        row = self.get_node(node_id)
        self.conn.execute("DELETE FROM node_fts WHERE rowid=?", (node_id,))
        self.conn.execute(
            "INSERT INTO node_fts(rowid,name,qualified_name,summary) VALUES(?,?,?,?)",
            (node_id, row["name"], row["qualified_name"], summary))

    def unsummarized(self, limit):
        return self.conn.execute(
            "SELECT * FROM nodes WHERE summary='' AND kind!='module' "
            "ORDER BY rank DESC LIMIT ?", (limit,)).fetchall()

    def summaries_for_file(self, path):
        return {r["qualified_name"]: (r["summary"], r["summary_hash"])
                for r in self.nodes_for_file(path) if r["summary"]}

    def set_ranks(self, ranks):
        self.conn.executemany("UPDATE nodes SET rank=? WHERE id=?",
                              [(v, k) for k, v in ranks.items()])

    def top_nodes(self, limit):
        return self.conn.execute(
            "SELECT * FROM nodes WHERE kind NOT IN ('file','module') "
            "ORDER BY rank DESC LIMIT ?", (limit,)).fetchall()

    def file_nodes(self):
        return self.conn.execute(
            "SELECT * FROM nodes WHERE kind='file' ORDER BY file_path").fetchall()

    def count_nodes(self):
        return self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    # --- usage telemetry (feeds retrieval reweighting) ---
    def log_usage(self, node_id):
        self.conn.execute(
            "INSERT INTO usage(node_id,cnt) VALUES(?,1) "
            "ON CONFLICT(node_id) DO UPDATE SET cnt=cnt+1", (node_id,))
        self.conn.commit()

    def usage_counts(self):
        return {r[0]: r[1] for r in self.conn.execute(
            "SELECT node_id, cnt FROM usage")}
