import hashlib
import time
from pathlib import Path

from cgraphy.db import GraphDB
from cgraphy.extract import extract_file
from cgraphy.resolver import resolve_refs
from cgraphy.walker import iter_files, relpath


def db_path(root) -> Path:
    return Path(root) / ".cgraphy" / "graph.db"


def module_qname(rel: str) -> str:
    p = Path(rel)
    return str(p.with_suffix("")).replace("/", ".")


def _snippet(source_lines, line_start, line_end):
    return "\n".join(source_lines[line_start - 1:line_end]) + "\n"


def ensure_gitignore(root: Path):
    gi = root / ".gitignore"
    if gi.is_file():
        text = gi.read_text(errors="replace")
        if ".cgraphy" not in text:
            gi.write_text(text.rstrip("\n") + "\n.cgraphy/\n")


def _schema_summary(path, text):
    """Deterministic data-lineage summary: make dataset schemas searchable."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        header = text.split("\n", 1)[0][:400]
        if "," in header:
            return f"CSV dataset — columns: {header}"
    elif suffix == ".sql":
        import re
        tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
                            r"[`\"']?(\w+)", text, re.I)
        if tables:
            return "SQL schema — defines tables: " + ", ".join(tables[:20])
    return None


def index_file(db, root, path, lang):
    rel = relpath(root, path)
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    old_summaries = db.summaries_for_file(rel)
    db.clear_file(rel)

    ex = extract_file(lang, raw, module_qname(rel))
    file_id = db.add_node("file", path.name, rel, language=lang, file_path=rel,
                          line_start=1, line_end=len(lines),
                          parse_error=1 if ex.parse_error else 0)
    schema = _schema_summary(path, text)
    if schema:
        db.update_summary(file_id, schema,
                          hashlib.sha256(raw).hexdigest())
    id_by_qname = {}
    for s in ex.syms:
        nid = db.add_node(s.kind, s.name, s.qualified_name, language=lang,
                          file_path=rel, line_start=s.line_start,
                          line_end=s.line_end, signature=s.signature)
        id_by_qname[s.qualified_name] = nid
        if s.qualified_name in old_summaries:
            summary, old_hash = old_summaries[s.qualified_name]
            new_hash = hashlib.sha256(
                _snippet(lines, s.line_start, s.line_end).encode()).hexdigest()
            if new_hash == old_hash:
                db.update_summary(nid, summary, old_hash)
    # containment: file -> top-level syms; class -> members
    for s in ex.syms:
        nid = id_by_qname[s.qualified_name]
        parent_q = s.qualified_name.rsplit(".", 1)[0]
        parent = id_by_qname.get(parent_q, file_id)
        db.add_edge(parent, nid, "contains")
    # refs (resolved later)
    for r in ex.refs:
        src = id_by_qname.get(r.source_qname, file_id)
        db.add_ref(src, r.kind, r.target_name)
    if rel in old_summaries:  # file-level summary
        summary, old_hash = old_summaries[rel]
        if hashlib.sha256(raw).hexdigest() == old_hash:
            db.update_summary(file_id, summary, old_hash)


def index_repo(root, git_history: bool = False) -> dict:
    root = Path(root).resolve()
    ensure_gitignore(root)
    db = GraphDB(db_path(root))
    stats = {"files_indexed": 0, "files_skipped": 0, "nodes": 0}
    seen = set()
    for path, lang in iter_files(root):
        rel = relpath(root, path)
        seen.add(rel)
        prev = db.get_file(rel)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if prev and mtime <= prev[1]:
            stats["files_skipped"] += 1
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if prev and prev[0] == h:
            db.set_file(rel, h, time.time())
            stats["files_skipped"] += 1
            continue
        index_file(db, root, path, lang)
        db.set_file(rel, h, time.time())
        stats["files_indexed"] += 1
    deleted = 0
    for gone in db.indexed_paths() - seen:
        db.clear_file(gone)
        db.delete_file(gone)
        deleted += 1
    changed = stats["files_indexed"] > 0 or deleted > 0
    if changed:  # post-passes are pointless (and costly at scale) otherwise
        resolve_refs(db)
        if git_history:
            from cgraphy.gitmine import mine_cochanges
            mine_cochanges(db, root)
        try:
            from cgraphy.pagerank import apply_pagerank
            apply_pagerank(db)
        except ImportError:
            pass
        from cgraphy.communities import apply_communities
        apply_communities(db)
        try:
            from cgraphy import semantic
            semantic.embed_missing(db)
        except Exception:
            pass
    stats["nodes"] = db.count_nodes()
    db.commit()
    db.close()
    return stats
