import os
import shutil
import time
import unittest
from pathlib import Path

import dag
import state
from dag import DAG, Task
from event_bus import clear


ROOT = Path(__file__).resolve().parent


class DAGHardeningTests(unittest.TestCase):
    def setUp(self):
        clear()
        self.tmpdir = ROOT / ".test_dag_db"
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.tmpdir.mkdir(exist_ok=True)
        self.original_db_file = state.DB_FILE
        state.DB_FILE = os.path.join(self.tmpdir, "milodo.db")

    def tearDown(self):
        clear()
        dag.TASK_TIMEOUT_SECONDS = 30
        state.DB_FILE = self.original_db_file
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_success_return_contract(self):
        result = DAG([Task("ok", lambda: None)]).run()

        self.assertEqual(result, {"success": True, "failed_task": None})

    def test_fail_fast_return_contract(self):
        calls = []

        def fail():
            calls.append("fail")
            raise Exception("boom")

        def after():
            calls.append("after")

        result = DAG([Task("fail", fail), Task("after", after)]).run()

        self.assertEqual(result, {"success": False, "failed_task": "fail"})
        self.assertEqual(calls, ["fail"])

    def test_rejects_dynamic_changes_during_run(self):
        current_dag = DAG()

        def mutate():
            current_dag.add_task(Task("late", lambda: None))

        current_dag.add_task(Task("mutate", mutate))
        result = current_dag.run()

        self.assertEqual(result, {"success": False, "failed_task": "mutate"})

    def test_task_timeout(self):
        dag.TASK_TIMEOUT_SECONDS = 0.05

        result = DAG([Task("slow", lambda: time.sleep(0.2))]).run()

        self.assertEqual(result, {"success": False, "failed_task": "slow"})


if __name__ == "__main__":
    unittest.main()
