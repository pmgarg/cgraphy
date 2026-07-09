from cgraphy.cli import build_parser


def test_parser_has_subcommands():
    p = build_parser()
    args = p.parse_args(["index", "/tmp/x", "--git-history"])
    assert args.command == "index" and args.git_history


def test_view_port_default():
    args = build_parser().parse_args(["view"])
    assert args.port == 8787
