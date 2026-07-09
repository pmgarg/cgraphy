RESOLVED_KINDS = ("calls", "imports", "inherits", "references")


def resolve_refs(db):
    db.delete_edges_of_kinds(RESOLVED_KINDS)
    rows = db.conn.execute(
        "SELECT id, kind, name, qualified_name, file_path FROM nodes").fetchall()
    by_qname, by_name = {}, {}
    for r in rows:
        by_qname[r["qualified_name"]] = r["id"]
        by_name.setdefault(r["name"], []).append(r["id"])
    module_files = {r["qualified_name"]: r["id"] for r in rows if r["kind"] == "file"}

    for ref in db.all_refs():
        target = ref["target_name"]
        tid = by_qname.get(target)
        if tid is None:
            suffix = [i for q, i in by_qname.items() if q.endswith("." + target)]
            if len(suffix) == 1:
                tid = suffix[0]
        if tid is None and target in by_name and len(by_name[target]) == 1:
            tid = by_name[target][0]
        if tid is None and ref["kind"] == "imports":
            dotted = target.replace("/", ".")
            for qn, fid in module_files.items():
                mq = qn.rsplit(".", 1)[0].replace("/", ".")
                if mq == dotted or mq.endswith("." + dotted) or dotted.endswith(mq):
                    tid = fid
                    break
        if tid is not None and tid != ref["source_id"]:
            db.add_edge(ref["source_id"], tid, ref["kind"])
    db.commit()
