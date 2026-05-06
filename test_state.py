import os
import sqlite3

import state_store
from dag import Task
from state_store import init_db, save_run, save_task


TEST_DB = "test_state_store.db"


def cleanup():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def main():
    cleanup()
    state_store.DB_FILE = TEST_DB

    print("[TEST] init_db creates tables")
    init_db()

    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    assert_true(table_exists(cursor, "runs"), "runs table was not created")
    assert_true(table_exists(cursor, "tasks"), "tasks table was not created")

    print("[TEST] save_run inserts a row")
    run_id = save_run(
        goal="test goal",
        decision={"intent": "test", "command": "run test"},
        success=True,
    )
    cursor.execute("SELECT goal, success FROM runs WHERE id = ?", (run_id,))
    run_row = cursor.fetchone()
    assert_true(run_row is not None, "run row was not inserted")
    assert_true(run_row[0] == "test goal", "run goal mismatch")
    assert_true(run_row[1] == 1, "run success mismatch")

    print("[TEST] save_task inserts tasks")
    task = Task("agent_execution", lambda: {"ok": True})
    task.status = "done"
    task.result = {"ok": True}
    task.error = None
    task_db_id = save_task(run_id, task)

    cursor.execute(
        "SELECT run_id, task_id, status, result, error FROM tasks WHERE id = ?",
        (task_db_id,),
    )
    task_row = cursor.fetchone()
    assert_true(task_row is not None, "task row was not inserted")
    assert_true(task_row[0] == run_id, "task run_id mismatch")
    assert_true(task_row[1] == "agent_execution", "task id mismatch")
    assert_true(task_row[2] == "done", "task status mismatch")
    assert_true('"ok": true' in task_row[3], "task result mismatch")
    assert_true(task_row[4] is None, "task error mismatch")

    print("[TEST] verify counts with SELECT queries")
    cursor.execute("SELECT COUNT(*) FROM runs")
    assert_true(cursor.fetchone()[0] == 1, "unexpected runs count")

    cursor.execute("SELECT COUNT(*) FROM tasks")
    assert_true(cursor.fetchone()[0] == 1, "unexpected tasks count")

    conn.close()
    cleanup()
    print("[TEST] state_store.py OK")


if __name__ == "__main__":
    main()
