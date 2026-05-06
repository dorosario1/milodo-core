"""
MILODO Phase 1 Test Suite

Rôle:
- Valider stabilité du système complet
- Tester CLI + DAG + SQLite sans dépendance externe

Couverture:

1. test_basic_execution
   → vérifie pipeline complet

2. test_invalid_command
   → sécurité input

3. test_multiple_runs
   → stabilité multi-exécution

4. test_failure_case
   → fail-fast DAG

5. test_database_integrity
   → cohérence runs/tasks

6. test_run_persistence
   → lien run → tasks

Stratégie technique:

- subprocess → exécution CLI réelle
- sqlite3 → validation DB directe
- unittest → standard Python

Isolation:

- backup automatique de milodo.db
- restauration après tests
- environnement simulé (fake docker)

Résultat attendu:

    python -m unittest test_milodo.py

    OK

Garantie:

- système fiable
- exécution reproductible
- aucun effet secondaire permanent
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MILODO = ROOT / "milodo.py"
DB = ROOT / "milodo.db"
DB_BACKUP = ROOT / "milodo.db.test_backup"
TEST_BIN = ROOT / ".test_bin"


class MilodoPhase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB.exists():
            if DB_BACKUP.exists():
                DB_BACKUP.unlink()
            DB.replace(DB_BACKUP)

        TEST_BIN.mkdir(exist_ok=True)
        (TEST_BIN / "docker.cmd").write_text("@echo off\necho [FAKE DOCKER] %*\n", encoding="utf-8")
        (TEST_BIN / "docker.bat").write_text("@echo off\necho [FAKE DOCKER] %*\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        if DB.exists():
            DB.unlink()
        if DB_BACKUP.exists():
            DB_BACKUP.replace(DB)
        shutil.rmtree(TEST_BIN, ignore_errors=True)

    def run_cli(self, command):
        env = {
            **os.environ,
            "PATH": f"{TEST_BIN}{os.pathsep}{os.environ.get('PATH', '')}",
            "PATHEXT": f".COM;.EXE;.BAT;.CMD{os.pathsep}{os.environ.get('PATHEXT', '')}",
            "PYTHONIOENCODING": "utf-8",
        }
        return subprocess.run(
            [sys.executable, str(MILODO), "run", command],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_basic_execution(self):
        result = self.run_cli("deploy")
        output = result.stdout + result.stderr

        self.assertIn("[START]", output)
        self.assertIn("[DONE]", output)
        self.assertIn("[DAG]", output)

    def test_invalid_command(self):
        result = self.run_cli("blabla")
        output = result.stdout + result.stderr

        self.assertIn("[AI] Unsafe or unknown command", output)
        self.assertIn("[MILODO] FAILED", output)

    def test_multiple_runs(self):
        for _ in range(5):
            result = self.run_cli("test")
            self.assertEqual(result.returncode, 0)
            self.assertIn("[MILODO] SUCCESS", result.stdout + result.stderr)

    def test_failure_case(self):
        code = (
            "from dag import DAG, Task\n"
            "def fail():\n"
            "    raise Exception('boom')\n"
            "DAG([Task('fail_task', fail)]).run()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = result.stdout + result.stderr

        self.assertIn("[FAILED]", output)
        self.assertIn("[DAG] FAILED", output)

    def test_database_integrity(self):
        self.run_cli("deploy")

        conn = sqlite3.connect(DB)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM runs")
        self.assertGreater(cursor.fetchone()[0], 0)

        cursor.execute("SELECT COUNT(*) FROM tasks")
        self.assertGreater(cursor.fetchone()[0], 0)

        cursor.execute("SELECT status FROM runs")
        run_statuses = [row[0] for row in cursor.fetchall()]
        self.assertTrue(all(status in ("success", "failed") for status in run_statuses))

        cursor.execute("SELECT status FROM tasks")
        task_statuses = [row[0] for row in cursor.fetchall()]
        self.assertTrue(all(status in ("done", "failed") for status in task_statuses))

        conn.close()

    def test_ai_integration(self):
        result = self.run_cli("please deploy my app")
        output = result.stdout + result.stderr

        self.assertIn("[AI] \u2192", output)
        self.assertIn("[Mapper]", output)
        self.assertIn("[START]", output)

    def test_run_persistence(self):
        self.run_cli("deploy")

        conn = sqlite3.connect(DB)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1")
        run_id = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tasks WHERE run_id = ?", (run_id,))
        self.assertGreater(cursor.fetchone()[0], 0)

        conn.close()


if __name__ == "__main__":
    unittest.main()
