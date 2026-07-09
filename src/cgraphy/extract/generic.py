from cgraphy import ts
from cgraphy.extract.base import Extraction, Sym

TYPE_LIKE = ("class", "struct", "trait", "interface", "impl", "module")
FUNC_LIKE = ("function", "method")
NAME_TYPES = {"identifier", "type_identifier", "constant", "field_identifier",
              "property_identifier", "name", "word"}


def _find_name(node, source):
    child = node.child_by_field_name("name")
    if child is not None:
        return ts.node_text(child, source)
    for ch in node.children:
        if ch.type in NAME_TYPES:
            return ts.node_text(ch, source)
    return None


def extract_generic(lang, source: bytes, module_qname: str) -> Extraction:
    ex = Extraction()
    tree = ts.parse(lang, source)
    stack = [(tree.root_node, [module_qname], None)]
    while stack:
        node, scope, scope_kind = stack.pop()
        t = node.type
        kind = None
        if any(k in t for k in FUNC_LIKE):
            kind = "method" if scope_kind == "class" else "function"
        elif any(k in t for k in TYPE_LIKE):
            kind = "class"
        new_scope, new_scope_kind = scope, scope_kind
        if kind:
            name = _find_name(node, source)
            if name:
                qname = ".".join(scope + [name])
                ex.syms.append(Sym(kind, name, qname,
                                   node.start_point[0] + 1, node.end_point[0] + 1,
                                   ts.node_text(node, source).split("\n", 1)[0].strip()))
                new_scope, new_scope_kind = scope + [name], kind
        for ch in node.children:
            stack.append((ch, new_scope, new_scope_kind))
    return ex
