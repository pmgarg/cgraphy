import json
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cgraphy.db import GraphDB
from cgraphy.indexer import db_path

STATIC = Path(__file__).parent / "static"


class _Server(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer.server_bind calls socket.getfqdn(), which hangs for tens
        # of seconds when reverse DNS is broken; we only ever serve localhost.
        socketserver.TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]


def graph_json(db, max_nodes=500):
    top = db.conn.execute(
        "SELECT * FROM nodes ORDER BY rank DESC, id LIMIT ?", (max_nodes,)).fetchall()
    included = {r["id"] for r in top}
    nodes = [{"data": {
        "id": str(r["id"]), "label": r["name"], "kind": r["kind"],
        "file": r["file_path"], "line": r["line_start"],
        "summary": r["summary"], "rank": r["rank"]}} for r in top]
    edges = [{"data": {"source": str(e["source_id"]), "target": str(e["target_id"]),
                       "kind": e["kind"]}}
             for e in db.all_edges()
             if e["source_id"] in included and e["target_id"] in included]
    return {"nodes": nodes, "edges": edges}


def serve_viewer(root, port=8787):
    root = Path(root).resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # reject DNS-rebinding: only answer requests addressed to localhost
            host = self.headers.get("Host", "").split(":", 1)[0]
            if host not in ("localhost", "127.0.0.1", "[::1]"):
                self.send_error(403)
                return
            if self.path == "/graph.json":
                db = GraphDB(db_path(root))
                body = json.dumps(graph_json(db)).encode()
                db.close()
                ctype = "application/json"
            elif self.path == "/cytoscape.min.js":
                body = (STATIC / "cytoscape.min.js").read_bytes()
                ctype = "text/javascript"
            else:
                body = (STATIC / "index.html").read_bytes()
                ctype = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    print(f"cgraphy viewer: http://localhost:{port}")
    _Server(("127.0.0.1", port), Handler).serve_forever()
