#!/usr/bin/env python3
"""Serve the project tree web UI. Usage: python scripts/tree_server.py [port]"""

from __future__ import annotations

import json
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))

from project_tree import fragments
from project_tree.model import list_projects, proposed_path

UI_DIR = PACKAGE_ROOT / "tools" / "tree-viewer"


class TreeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, format, *args):
        if args and str(args[0]).startswith("GET /api"):
            super().log_message(format, *args)

    def do_GET(self):
        if self.path == "/api/projects":
            self._json_response(list_projects())
            return
        if self.path.startswith("/api/tree/"):
            project = unquote(self.path.removeprefix("/api/tree/").strip("/"))
            try:
                self._json_response(self._load_tree(project))
            except FileNotFoundError:
                self.send_error(404, f"Project not found: {project}")
            return
        if self.path == "/":
            self.path = "/index.html"
        if "?" in self.path:
            self.path = self.path.split("?", 1)[0]
        return super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _load_tree(self, name: str) -> dict:
        from project_tree.model import nodes_path, resolve_project_name

        name = resolve_project_name(name)
        path = nodes_path(name)
        if not path.exists():
            raise FileNotFoundError(name)
        with path.open() as f:
            data = yaml.safe_load(f)
        data["pending"] = proposed_path(name).exists()
        try:
            data = fragments.compose_tree(data, name)
        except (FileNotFoundError, ValueError) as exc:
            data["compose_error"] = str(exc)
        return data

    def _json_response(self, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), TreeHandler)
    projects = list_projects()
    q = f"?project={projects[0]}" if projects else ""
    url = f"http://127.0.0.1:{port}/{q}"
    print(f"Tree viewer at {url}")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
