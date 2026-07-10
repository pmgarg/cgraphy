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
    idx.add_argument("--summarize", action="store_true")
    srv = sub.add_parser("serve", help="run the MCP server (stdio)")
    srv.add_argument("path", nargs="?", default=".")
    view = sub.add_parser("view", help="serve the local graph viewer")
    view.add_argument("path", nargs="?", default=".")
    view.add_argument("--port", type=int, default=8787)
    ini = sub.add_parser("init", help="wire cgraphy into AI assistants for this repo")
    ini.add_argument("path", nargs="?", default=".")
    ini.add_argument("--no-enrich", action="store_true",
                     help="skip automatic semantic enrichment")
    dif = sub.add_parser("diff", help="blast radius of uncommitted changes")
    dif.add_argument("path", nargs="?", default=".")
    enr = sub.add_parser("enrich", help="summarize symbols via your agent CLI")
    enr.add_argument("path", nargs="?", default=".")
    enr.add_argument("--max-nodes", type=int, default=400)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        build_parser().print_help()
        return 1
    if args.command == "index":
        from cgraphy.indexer import index_repo
        stats = index_repo(args.path, git_history=args.git_history)
        print(f"indexed {stats['files_indexed']} files "
              f"({stats['files_skipped']} unchanged), {stats['nodes']} nodes")
        if args.summarize:
            from cgraphy.db import GraphDB
            from cgraphy.indexer import db_path
            from cgraphy.summarize import api_summarize
            db = GraphDB(db_path(args.path))
            n = api_summarize(db, args.path)
            db.close()
            print(f"summarized {n} symbols")
        return 0
    if args.command == "serve":
        from cgraphy.server import run_server
        run_server(args.path)
        return 0
    if args.command == "view":
        from cgraphy.viewer import serve_viewer
        serve_viewer(args.path, port=args.port)
        return 0
    if args.command == "init":
        import shutil as _sh

        from cgraphy.indexer import index_repo
        from cgraphy.init_cmd import init_project
        print(init_project(args.path))
        stats = index_repo(args.path, git_history=True)
        print(f"indexed {stats['files_indexed']} files, {stats['nodes']} nodes")
        if not args.no_enrich and _sh.which("claude"):
            from cgraphy.enrich_cmd import enrich_repo
            print("enriching top symbols via claude CLI (uses your plan; "
                  "skip with --no-enrich)...")
            n = enrich_repo(args.path)
            print(f"summarized {n} symbols")
        return 0
    if args.command == "diff":
        from cgraphy.db import GraphDB
        from cgraphy.diffctx import diff_context
        from cgraphy.indexer import db_path, index_repo
        index_repo(args.path)
        db = GraphDB(db_path(args.path))
        print(diff_context(db, args.path))
        db.close()
        return 0
    if args.command == "enrich":
        from cgraphy.enrich_cmd import enrich_repo
        print(f"summarized {enrich_repo(args.path, max_nodes=args.max_nodes)} "
              "symbols")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
