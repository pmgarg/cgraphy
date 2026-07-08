from cgraphy import ts

SRC = b"def hello(name):\n    return name\n"


def test_parse_and_match_python():
    tree = ts.parse("python", SRC)
    matches = ts.run_matches(
        "python", "(function_definition name: (identifier) @name) @def", tree.root_node)
    assert len(matches) == 1
    m = matches[0]
    assert ts.node_text(m["name"][0], SRC) == "hello"
    assert m["def"][0].start_point[0] == 0
