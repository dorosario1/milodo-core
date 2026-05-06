"""
MILODO Event Bus — Phase 4 Real-Time Bridge

Architecture multi-process:

    DAG
    → event_bus.emit()
    → SQLite events table
    → ws_server polling every 1s
    → WebSocket broadcast
    → React UI update

emit() has two responsibilities:
- persist every event into SQLite so other processes can observe it
- keep the original in-memory subscriber dispatch for same-process handlers

Events are stored in the events table as:
- type: event name
- payload: JSON string
- processed: 0 until ws_server broadcasts it, then 1

The in-memory subscriber registry remains synchronous and deterministic.
If one handler fails, the error is logged and the remaining handlers continue.
"""

import json
import sqlite3


_subscribers = {}


def _init_events_table():
    """Create or migrate the SQLite events bridge table without deleting data."""
    conn = sqlite3.connect("milodo.db")
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

    conn.commit()
    conn.close()


def _persist_event(event_name, payload):
    """Store an emitted event for multi-process consumers such as ws_server."""
    _init_events_table()
    conn = sqlite3.connect("milodo.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO events (type, payload) VALUES (?, ?)",
        (event_name, json.dumps(payload or {})),
    )

    conn.commit()
    conn.close()


def subscribe(event_name: str, handler: callable):
    if event_name not in _subscribers:
        _subscribers[event_name] = []

    _subscribers[event_name].append(handler)


def emit(event_name: str, payload: dict | None = None):
    """Persist the event, then dispatch it to same-process subscribers."""
    _persist_event(event_name, payload)

    for handler in _subscribers.get(event_name, []):
        try:
            handler(payload)
        except Exception as error:
            print(f"[EVENT ERROR] {event_name}: {error}")


def clear():
    _subscribers.clear()
