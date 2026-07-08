import argparse
import sys

from cgraphy import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cgraphy")
    p.add_argument("--version", action="version", version=f"cgraphy {__version__}")
    sub = p.add_subparsers(dest="command")
    idx = sub.add_parser("index", help="build/update the knowledge graph")
    idx.add_argument("path", nargs="?", default=".")
    idx.add_argument("--git-history", action="store_true")
    srv = sub.add_parser("serve", help="run the MCP server (stdio)")
    srv.add_argument("path", nargs="?", default=".")
    view = sub.add_parser("view", help="serve the local graph viewer")
    view.add_argument("path", nargs="?", default=".")
    view.add_argument("--port", type=int, default=8787)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        build_parser().print_help()
        return 1
    print(f"{args.command}: not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
