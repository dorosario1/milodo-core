import unittest

import scheduler
from event_bus import clear, emit


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        clear()
        scheduler._triggered = False
        self.calls = []
        self.original_run_command = scheduler.run_command
        scheduler.run_command = self.fake_run_command
        scheduler.init_scheduler()

    def tearDown(self):
        scheduler.run_command = self.original_run_command
        scheduler._triggered = False
        clear()

    def fake_run_command(self, command):
        self.calls.append(command)

    def test_run_failed_triggers_retry(self):
        emit("run_failed", {})

        self.assertEqual(self.calls, ["deploy"])

    def test_task_failed_triggers_retry(self):
        emit("task_failed", {"task": "build", "error": "boom"})

        self.assertEqual(self.calls, ["deploy"])

    def test_no_infinite_loop(self):
        emit("run_failed", {})
        emit("run_failed", {})

        self.assertEqual(self.calls, ["deploy"])


if __name__ == "__main__":
    unittest.main()
