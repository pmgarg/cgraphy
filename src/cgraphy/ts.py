import sys

from tree_sitter_language_pack import get_language, get_parser  # noqa: F401


def parse(lang: str, source: bytes):
    return get_parser(lang).parse(source)


def _query(lang: str, query_src: str):
    language = get_language(lang)
    try:
        return language.query(query_src)          # tree-sitter <= 0.23
    except AttributeError:
        from tree_sitter import Query
        return Query(language, query_src)          # tree-sitter >= 0.24


def run_matches(lang: str, query_src: str, root):
    q = _query(lang, query_src)
    if hasattr(q, "matches"):
        raw = q.matches(root)
    else:                                          # tree-sitter >= 0.24
        from tree_sitter import QueryCursor
        raw = QueryCursor(q).matches(root)
    out = []
    for _pattern, caps in raw:
        out.append({k: (v if isinstance(v, list) else [v]) for k, v in caps.items()})
    return out


def run_captures(lang: str, query_src: str, root):
    pairs = []
    for caps in run_matches(lang, query_src, root):
        for name, nodes in caps.items():
            for n in nodes:
                pairs.append((name, n))
    return pairs


def node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


if __name__ == "__main__":
    from pathlib import Path

    from cgraphy.walker import LANGUAGE_BY_EXT
    p = Path(sys.argv[1])
    lang = LANGUAGE_BY_EXT[p.suffix.lower()]
    tree = parse(lang, p.read_bytes())
    print(str(tree.root_node))
