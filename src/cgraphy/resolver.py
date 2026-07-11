RESOLVED_KINDS = ("calls", "imports", "inherits", "references")


def resolve_refs(db):
    db.delete_edges_of_kinds(RESOLVED_KINDS)
    rows = db.conn.execute(
        "SELECT id, kind, name, qualified_name, file_path FROM nodes").fetchall()
    by_qname, by_name = {}, {}
    for r in rows:
        by_qname[r["qualified_name"]] = r["id"]
        by_name.setdefault(r["name"], []).append((r["qualified_name"], r["id"]))
    # module files indexed by the last dotted component of their module path,
    # so import resolution never scans the whole file list (monorepo scale)
    module_by_last = {}
    for r in rows:
        if r["kind"] != "file":
            continue
        mq = r["qualified_name"].rsplit(".", 1)[0].replace("/", ".")
        module_by_last.setdefault(mq.rsplit(".", 1)[-1], []).append((mq, r["id"]))

    for ref in db.all_refs():
        target = ref["target_name"]
        tid = by_qname.get(target)
        if tid is None:
            # candidates share the target's last component; check only those
            cands = by_name.get(target.rsplit(".", 1)[-1], [])
            suffix = [i for q, i in cands if q.endswith("." + target)]
            if len(suffix) == 1:
                tid = suffix[0]
            elif tid is None and len(cands) == 1 and "." not in target:
                tid = cands[0][1]
        if tid is None and ref["kind"] == "imports":
            dotted = target.replace("/", ".")
            for mq, fid in module_by_last.get(dotted.rsplit(".", 1)[-1], []):
                if mq == dotted or mq.endswith("." + dotted) \
                        or dotted.endswith(mq):
                    tid = fid
                    break
        if tid is not None and tid != ref["source_id"]:
            db.add_edge(ref["source_id"], tid, ref["kind"])
    db.commit()
