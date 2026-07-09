from cgraphy import ts
from cgraphy.extract.base import Extraction, Ref, Sym
from cgraphy.extract.langs import IMPORT_CLEANERS, TIER1


def _first_line(node, source: bytes) -> str:
    return ts.node_text(node, source).split("\n", 1)[0].strip()


def extract_tier1(lang: str, source: bytes, module_qname: str) -> Extraction:
    spec = TIER1[lang]
    tree = ts.parse(lang, source)
    root = tree.root_node
    ex = Extraction()

    # 1. Definitions: (byte_start, byte_end, base_kind, name, node)
    defs = []
    for caps in ts.run_matches(lang, spec.defs_query, root):
        name_nodes = caps.get("name")
        def_key = next((k for k in caps if k.startswith("def")), None)
        if not name_nodes or not def_key:
            continue
        dnode = caps[def_key][0]
        base_kind = def_key.split(".", 1)[1] if "." in def_key else "function"
        defs.append((dnode.start_byte, dnode.end_byte, base_kind,
                     ts.node_text(name_nodes[0], source), dnode))
    defs.sort(key=lambda d: (d[0], -d[1]))

    def enclosing(byte_off, end_off=None):
        """Innermost def strictly containing [byte_off, end_off)."""
        end_off = byte_off if end_off is None else end_off
        best = None
        for s, e, kind, name, node in defs:
            if s < byte_off and end_off <= e:
                if best is None or s > best[0]:
                    best = (s, e, kind, name, node)
        return best

    # 2. Qualified names via enclosure chains.
    qname_by_span = {}
    for s, e, kind, name, node in defs:
        parts = [name]
        cur = enclosing(s, e)
        guard = 0
        while cur and guard < 50:
            parts.append(cur[3])
            cur = enclosing(cur[0], cur[1])
            guard += 1
        parts.append(module_qname)
        qname = ".".join(reversed(parts))
        qname_by_span[(s, e)] = qname
        outer = enclosing(s, e)
        real_kind = "method" if (kind == "function" and outer
                                 and outer[2] == "class") else kind
        ex.syms.append(Sym(real_kind, name, qname,
                           node.start_point[0] + 1, node.end_point[0] + 1,
                           _first_line(node, source)))

    def source_qname(node) -> str:
        outer = enclosing(node.start_byte, node.end_byte)
        return qname_by_span[(outer[0], outer[1])] if outer else module_qname

    # 3. References.
    clean = IMPORT_CLEANERS.get(lang, lambda t: t)
    for cap, node in ts.run_captures(lang, spec.refs_query, root):
        text = ts.node_text(node, source).strip("\"'<>")
        if cap == "call.name":
            ex.refs.append(Ref("calls", source_qname(node), text))
        elif cap == "import.module":
            ex.refs.append(Ref("imports", module_qname, clean(text)))
        elif cap == "inherit.name":
            ex.refs.append(Ref("inherits", source_qname(node), text))
    return ex
