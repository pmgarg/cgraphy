"""Optional hybrid semantic search (install extra: cgraphy[semantic]).

Uses model2vec static embeddings (tiny, CPU-only, no torch) to close the
vocabulary gap between natural-language queries and code identifiers — the
weakness our SWE-bench evaluation exposed for pure lexical search. Vectors
live in the same SQLite file; fusion with FTS uses reciprocal-rank fusion,
which needs no score calibration.
"""
import math
import os
from array import array

_model = None
_tried = False


def _get_model():
    global _model, _tried
    if _model is None and not _tried:
        _tried = True
        try:
            from model2vec import StaticModel
            _model = StaticModel.from_pretrained(
                os.environ.get("CGRAPHY_EMBED_MODEL", "minishlab/potion-base-8M"))
        except Exception:
            _model = None
    return _model


def available() -> bool:
    return _get_model() is not None


def _node_text(r) -> str:
    return " ".join(x for x in (r["name"], r["qualified_name"],
                                r["signature"], r["summary"]) if x)


def embed_missing(db, batch=1024) -> int:
    """Embed nodes that have no vector yet. Returns count embedded."""
    model = _get_model()
    if model is None:
        return 0
    rows = db.conn.execute(
        "SELECT id, name, qualified_name, signature, summary FROM nodes "
        "WHERE id NOT IN (SELECT node_id FROM vectors)").fetchall()
    total = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        vecs = model.encode([_node_text(r) for r in chunk])
        db.conn.executemany(
            "INSERT OR REPLACE INTO vectors(node_id, vec) VALUES(?,?)",
            [(r["id"], array("f", [float(x) for x in v]).tobytes())
             for r, v in zip(chunk, vecs)])
        total += len(chunk)
    db.commit()
    return total


def semantic_ranked(db, query, limit=50):
    """Node ids ranked by cosine similarity to the query."""
    model = _get_model()
    if model is None:
        return []
    qv = [float(x) for x in model.encode([query])[0]]
    qn = math.sqrt(sum(x * x for x in qv)) or 1.0
    scored = []
    for node_id, blob in db.conn.execute("SELECT node_id, vec FROM vectors"):
        v = array("f")
        v.frombytes(blob)
        dot = sum(a * b for a, b in zip(qv, v))
        n = math.sqrt(sum(b * b for b in v)) or 1.0
        scored.append((dot / (qn * n), node_id))
    scored.sort(reverse=True)
    return [nid for _s, nid in scored[:limit]]


def hybrid_search(db, query, limit=12, k=60):
    """Reciprocal-rank fusion of FTS and semantic rankings."""
    fts_rows = db.search_fts(query, 50)
    sem_ids = semantic_ranked(db, query, 50)
    rrf = {}
    for i, r in enumerate(fts_rows):
        rrf[r["id"]] = rrf.get(r["id"], 0.0) + 1.0 / (k + i + 1)
    for i, nid in enumerate(sem_ids):
        rrf[nid] = rrf.get(nid, 0.0) + 1.0 / (k + i + 1)
    order = sorted(rrf, key=lambda nid: -rrf[nid])[:limit]
    return [db.get_node(nid) for nid in order]
