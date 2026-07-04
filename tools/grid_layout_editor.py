#!/usr/bin/env python3
"""Dev tool: arrange each ship's cargo grids to match their real in-ship
positions, and save the result into ships_cargo_grids.json.

Not part of the shipped app — nothing under tools/ is bundled by app.spec.
The saved `layout` field is optional viewer metadata: the packing engine
ignores it, and grids without one keep the legacy auto-row presentation.

Usage:
    python tools/grid_layout_editor.py [--port 8620] [--no-browser]

Serves the repo root (so the editor page can reuse frontend/vendor/three)
and exposes POST /api/save, which validates the document, backs up the
current ships_cargo_grids.json to ships_cargo_grids.json.bak, and writes
the new version.
"""
import argparse
import json
import shutil
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPS_FILE = REPO_ROOT / "ships_cargo_grids.json"
BACKUP_FILE = REPO_ROOT / "ships_cargo_grids.json.bak"
EDITOR_PAGE = "/tools/grid_layout_editor.html"

sys.path.insert(0, str(REPO_ROOT / "src"))
from packing_core.grid_utils import normalize_grids  # noqa: E402


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", EDITOR_PAGE)
            self.end_headers()
            return
        super().do_GET()

    def _reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/save":
            self._reply(404, {"ok": False, "error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or not isinstance(data.get("ships"), list):
                raise ValueError("payload must be a {ships: [...]} document")
            for ship in data["ships"]:
                if not isinstance(ship.get("name"), str):
                    raise ValueError("every ship needs a name")
                normalize_grids(ship.get("grids", []))  # validates dims/blocked/layout
        except Exception as e:
            self._reply(400, {"ok": False, "error": str(e)})
            return

        if SHIPS_FILE.exists():
            shutil.copy2(SHIPS_FILE, BACKUP_FILE)
        SHIPS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self._reply(200, {"ok": True, "backup": BACKUP_FILE.name})

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet; errors still raise


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8620)
    ap.add_argument("--no-browser", action="store_true",
                    help="don't open the editor page automatically")
    args = ap.parse_args()

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}{EDITOR_PAGE}"
    print(f"Grid layout editor: {url}")
    print(f"Editing: {SHIPS_FILE}")
    print("Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
