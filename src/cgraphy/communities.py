"""Subsystem detection via deterministic label propagation on the file graph.

Files are nodes; any edge between symbols projects onto their files. Ten
rounds of synchronous label propagation (ties broken by smallest label) give
stable communities without external dependencies. Symbols inherit their
file's community.
"""
from collections import Counter


def apply_communities(db, rounds=10):
    rows = db.conn.execute(
        "SELECT id, kind, file_path FROM nodes").fetchall()
    file_of = {r["id"]: r["file_path"] for r in rows}
    file_ids = {r["file_path"]: r["id"] for r in rows if r["kind"] == "file"}

    adj = {fid: set() for fid in file_ids.values()}
    for e in db.all_edges():
        if e["kind"] == "contains":
            continue
        fa = file_ids.get(file_of.get(e["source_id"]))
        fb = file_ids.get(file_of.get(e["target_id"]))
        if fa and fb and fa != fb:
            adj[fa].add(fb)
            adj[fb].add(fa)

    label = {fid: fid for fid in adj}
    for _ in range(rounds):
        changed = False
        for fid in sorted(adj):
            if not adj[fid]:
                continue
            counts = Counter(label[n] for n in adj[fid])
            top = max(counts.values())
            best = min(l for l, c in counts.items() if c == top)
            if best != label[fid]:
                label[fid] = best
                changed = True
        if not changed:
            break

    by_path = {path: label.get(fid, fid) for path, fid in file_ids.items()}
    db.conn.executemany(
        "UPDATE nodes SET community=? WHERE file_path=?",
        [(comm, path) for path, comm in by_path.items()])
    db.commit()


def subsystems(db, limit=6, files_per=4):
    """[(community_id, [file rows sorted by rank])] for the largest clusters."""
    rows = db.conn.execute(
        "SELECT * FROM nodes WHERE kind='file' AND community!=0 "
        "ORDER BY community, rank DESC").fetchall()
    groups = {}
    for r in rows:
        groups.setdefault(r["community"], []).append(r)
    ranked = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    return [(cid, members[:files_per], len(members))
            for cid, members in ranked[:limit] if len(members) >= 2]
