import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any


DB_FILE = "milodo.db"


@contextmanager
def connection():
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def init_db():
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                decision TEXT NOT NULL,
                success INTEGER NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tasks_run_id
            ON tasks(run_id)
            """
        )


def save_run(goal, decision, success):
    init_db()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO runs (goal, decision, success, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(goal), to_json(decision), 1 if success else 0, time.time()),
        )
        return cursor.lastrowid


def save_task(run_id, task):
    init_db()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (run_id, task_id, status, result, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                str(task.id),
                str(task.status),
                to_json(task.result),
                None if task.error is None else str(task.error),
            ),
        )
        return cursor.lastrowid
