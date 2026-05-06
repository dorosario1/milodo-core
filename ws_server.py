"""
MILODO WebSocket Server — Phase 4 Real-Time Bridge

Architecture:

    DAG
    → event_bus.emit()
    → SQLite events table
    → ws_server polling every 1s
    → WebSocket broadcast
    → React UI update

The server opens a WebSocket endpoint on 127.0.0.1:4001 and keeps the
existing WebSocket client protocol unchanged.

Multi-process bridge:
- CLI/DAG processes write events to SQLite through event_bus.emit()
- ws_server polls events where processed = 0 every second
- each event is broadcast as:
    {
      "event": "...",
      "payload": {...}
    }
- after broadcast, the row is marked processed = 1

The in-memory Event Bus subscription is still used for events emitted inside
the ws_server process. SQLite polling is what makes events visible across
separate Python processes.
"""

import base64
import hashlib
import json
import socket
import sqlite3
import threading
import time

from event_bus import subscribe


HOST = "127.0.0.1"
PORT = 4001
DB_FILE = "milodo.db"
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
EVENTS = (
    "task_started",
    "task_done",
    "task_failed",
    "run_started",
    "run_success",
    "run_failed",
)

clients = []
last_cleanup = 0


def _init_events_table():
    """Create or migrate the SQLite events bridge table without deleting data."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER DEFAULT 0
        )
        """)

        cursor.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}
        if "type" not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN type TEXT")
        if "payload" not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN payload TEXT")
        if "created_at" not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN created_at TIMESTAMP")
        if "processed" not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN processed INTEGER DEFAULT 0")

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_processed
        ON events(processed)
        """)

        conn.commit()
    finally:
        if conn:
            conn.close()


def _handshake(client):
    request = client.recv(4096).decode("utf-8", errors="ignore")
    headers = {}

    for line in request.split("\r\n")[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

    websocket_key = headers.get("sec-websocket-key")
    if not websocket_key:
        raise ValueError("missing websocket key")

    accept = base64.b64encode(
        hashlib.sha1((websocket_key + GUID).encode("utf-8")).digest()
    ).decode("ascii")

    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    )
    client.sendall(response.encode("utf-8"))


def _encode_frame(message):
    payload = message.encode("utf-8")
    length = len(payload)

    if length < 126:
        header = bytes([0x81, length])
    elif length < 65536:
        header = bytes([0x81, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([0x81, 127]) + length.to_bytes(8, "big")

    return header + payload


def broadcast(event_name, payload=None):
    """Broadcast one event payload to all connected WebSocket clients."""
    print(f"[WS] broadcast {event_name}")
    message = json.dumps({
        "event": event_name,
        "payload": payload or {},
    })
    frame = _encode_frame(message)

    for client in clients[:]:
        try:
            client.sendall(frame)
        except OSError:
            if client in clients:
                clients.remove(client)
            try:
                client.close()
            except OSError:
                pass


def _make_handler(event_name):
    def handler(payload):
        broadcast(event_name, payload)

    return handler


def _client_loop(client):
    try:
        _handshake(client)
        clients.append(client)
        print("[WS] client connected")

        while True:
            data = client.recv(1024)
            if not data:
                break
    except Exception:
        pass
    finally:
        if client in clients:
            clients.remove(client)
        try:
            client.close()
        except OSError:
            pass
        print("[WS] client disconnected")


def init_event_bridge():
    for event_name in EVENTS:
        subscribe(event_name, _make_handler(event_name))


def poll_sqlite_events():
    """Poll SQLite every second, broadcast unprocessed events, then mark them processed."""
    global last_cleanup
    _init_events_table()

    while True:
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            now = time.time()
            if now - last_cleanup >= 30:
                cursor.execute("""
                DELETE FROM events
                WHERE processed = 1
                AND created_at < datetime('now', '-5 minutes')
                """)
                last_cleanup = now

            cursor.execute(
                "SELECT id, type, payload FROM events WHERE processed = 0 ORDER BY id ASC LIMIT 100"
            )
            rows = cursor.fetchall()

            for row in rows:
                try:
                    payload = json.loads(row["payload"] or "{}")
                except json.JSONDecodeError:
                    payload = {}

                broadcast(row["type"], payload)
                cursor.execute(
                    "UPDATE events SET processed = 1 WHERE id = ?",
                    (row["id"],),
                )

            conn.commit()
        except Exception as error:
            print(f"[WS] event poll error: {error}")
        finally:
            if conn:
                conn.close()

        time.sleep(1)


def run_server():
    init_event_bridge()
    poll_thread = threading.Thread(target=poll_sqlite_events, daemon=True)
    poll_thread.start()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"[WS] ws://{HOST}:{PORT}")

    while True:
        client, _ = server.accept()
        thread = threading.Thread(target=_client_loop, args=(client,), daemon=True)
        thread.start()


if __name__ == "__main__":
    run_server()
