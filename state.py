"""
MILODO State Store (SQLite) — Phase 4 Real-Time Bridge

Rôle:
- Persister chaque exécution (run)
- Tracer les tâches du DAG (tasks)
- Créer le pont d’événements multi-process pour la UI temps réel

Base:
- Fichier local: milodo.db
- Aucun ORM (sqlite3 natif)
- Migrations sûres sans suppression de données

Architecture temps réel:

    DAG
    → event_bus.emit()
    → SQLite events table
    → ws_server polling every 1s
    → WebSocket broadcast
    → React UI update

Tables principales:

runs:
- id (PK)
- command (texte exécuté)
- status (pending | success | failed)
- created_at (timestamp auto)

tasks:
- id (PK)
- run_id (FK logique)
- name (nom tâche)
- status (pending | done | failed)
- error (texte nullable)

events:
- id (PK)
- type (nom événement)
- payload (JSON texte)
- created_at (timestamp auto)
- processed (0 = à diffuser, 1 = diffusé)

Cycle de vie state:

1. init_db()
   → initialise la base si absente
   → migre les colonnes manquantes avec ALTER TABLE

2. create_run(command)
   → crée une exécution
   → retourne run_id

3. create_task(run_id, name)
   → crée une tâche liée au run

4. update_task(task_id, status, error=None)
   → met à jour statut tâche

5. update_run(run_id, status)
   → met à jour statut global

Garanties:

- Ne supprime jamais la base
- Ne supprime jamais les données existantes
- Ajoute uniquement les colonnes manquantes
- Connexion SQLite ouverte/fermée par appel

Logs:
- Aucun log interne (respect séparation responsabilités)
- Logs gérés par DAG, Event Bus et WebSocket selon leur rôle

Risques connus:

- Transactions explicites avec rollback sur erreur
- Liens run_id vérifiés avant création de tâche
- Pas de purge historique
"""

from contextlib import contextmanager
import sqlite3


DB_FILE = "milodo.db"


@contextmanager
def transaction():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")

    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create runs, tasks, and events tables, then safely migrate missing columns."""
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            name TEXT,
            status TEXT,
            error TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER DEFAULT 0
        )
        """)

        cursor.execute("PRAGMA table_info(runs)")
        run_columns = {row[1] for row in cursor.fetchall()}
        if "command" not in run_columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN command TEXT")
        if "created_at" not in run_columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN created_at TIMESTAMP")

        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = {row[1] for row in cursor.fetchall()}
        if "run_id" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN run_id INTEGER")
        if "name" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN name TEXT")
        if "status" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN status TEXT")
        if "error" not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN error TEXT")

        cursor.execute("PRAGMA table_info(events)")
        event_columns = {row[1] for row in cursor.fetchall()}
        if "type" not in event_columns:
            cursor.execute("ALTER TABLE events ADD COLUMN type TEXT")
        if "payload" not in event_columns:
            cursor.execute("ALTER TABLE events ADD COLUMN payload TEXT")
        if "created_at" not in event_columns:
            cursor.execute("ALTER TABLE events ADD COLUMN created_at TIMESTAMP")
        if "processed" not in event_columns:
            cursor.execute("ALTER TABLE events ADD COLUMN processed INTEGER DEFAULT 0")

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_processed
        ON events(processed)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_run_id
        ON tasks(run_id)
        """)


def create_run(command):
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM runs WHERE command = ? AND status = ?",
            (command, "pending")
        )
        existing_run = cursor.fetchone()
        if existing_run:
            return existing_run[0]

        cursor.execute(
            "INSERT INTO runs (command, status) VALUES (?, ?)",
            (command, "pending")
        )

        return cursor.lastrowid


def update_run(run_id, status):
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE runs SET status = ? WHERE id = ?",
            (status, run_id)
        )

        if cursor.rowcount != 1:
            raise ValueError(f"run_id not found: {run_id}")


def create_task(run_id, name):
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM runs WHERE id = ?", (run_id,))
        if cursor.fetchone() is None:
            raise ValueError(f"run_id not found: {run_id}")

        cursor.execute(
            "INSERT INTO tasks (run_id, name, status) VALUES (?, ?, ?)",
            (run_id, name, "pending")
        )

        return cursor.lastrowid


def update_task(task_id, status, error=None):
    with transaction() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE tasks SET status = ?, error = ? WHERE id = ?",
            (status, error, task_id)
        )

        if cursor.rowcount != 1:
            raise ValueError(f"task_id not found: {task_id}")
