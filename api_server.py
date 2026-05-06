"""
MILODO State API — Phase 4 (SQLite Bridge)

Rôle:
- Exposer les données SQLite à la UI React
- Fournir un snapshot des runs et tasks

Endpoint:

GET /state

Réponse:

{
  "runs": [...],
  "tasks": [...]
}

---

Données:

runs:
- id
- command
- status
- created_at

tasks:
- id
- run_id
- name
- status
- error

---

Architecture:

React UI
→ HTTP GET /state
→ SQLite
→ JSON

---

Comportement:

- Lecture directe DB
- Pas de cache
- Pas de logique métier
- Pas d’auth

---

Garanties:

- Simple
- Déterministe
- Sans dépendance externe

---

Contraintes Phase 4:

- Pas de temps réel
- Pas de WebSocket
- Pas de POST/PUT

---

Limites:

- Pas de pagination
- Pas de filtrage
- Pas de sécurité

---

Évolution future:

- API REST complète
- Authentification
- WebSocket (live updates)
"""

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer


DB_FILE = "milodo.db"
HOST = "127.0.0.1"
PORT = 4000


def fetch_state():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5")
    runs = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM tasks")
    tasks = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        "runs": runs,
        "tasks": tasks,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._send_headers()

    def do_GET(self):
        if self.path != "/state":
            self._send_headers(404)
            self.wfile.write(json.dumps({"error": "not found"}).encode("utf-8"))
            return

        try:
            payload = fetch_state()
            self._send_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        except Exception as error:
            self._send_headers(500)
            self.wfile.write(json.dumps({"error": str(error)}).encode("utf-8"))


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"[API] http://{HOST}:{PORT}/state")
    server.serve_forever()
