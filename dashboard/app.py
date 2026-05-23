from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import urlparse

from data_loader import load_dashboard_data


ROOT = Path(__file__).resolve().parent
HOST = "localhost"
PORT = 8050


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(render_dashboard())
            return
        if path == "/data.json":
            self._send_json(load_dashboard_data())
            return
        if path == "/static/style.css":
            self._send_static(ROOT / "static" / "style.css", "text/css")
            return
        self.send_error(404)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, data) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def render_dashboard() -> str:
    data = load_dashboard_data()
    template = Template((ROOT / "templates" / "index.html").read_text(encoding="utf-8"))
    return template.safe_substitute(
        soak_stable=str(data["soak"].get("long_term", {}).get("stable", "unknown")).lower(),
        memory_records=data["memory"]["records"],
        memory_executions=data["memory"]["executions"],
        rollback_history=data["memory"]["rollback_history"],
        strategy_rankings=_json_block(data["benchmark"]["strategy_scores"]),
        runtime_scores=_json_block(data["benchmark"]["runtime_compatibility"]),
        transfer_scores=_json_block(data["transferability"]),
        ecommerce_patterns=_json_block(data["knowledge"]["ecommerce_patterns"]),
        ui_fixes=_json_block(data["knowledge"]["ui_fixes"]),
        snapshots=_json_block(data["snapshots"]),
        raw_json=_json_block(data),
    )


def _json_block(data) -> str:
    return json.dumps(data, indent=2)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"MILODO dashboard read-only: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

