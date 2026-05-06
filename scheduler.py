"""
MILODO Smart Scheduler

Minimal scheduler layer on top of DAG execution.
"""

import time


class Scheduler:
    def __init__(self, dag):
        self.dag = dag

    def run(self):
        completed = 0
        failed = 0

        try:
            self.dag._reset_tasks()
            ordered_tasks = self.dag._topological_order()
        except Exception as error:
            print(f"[SCHEDULER] Failed DAG: {error}")
            return {
                "success": False,
                "completed": completed,
                "failed": 1,
            }

        for index, task in enumerate(ordered_tasks):
            blocked = any(
                self.dag.tasks[dependency_id].status != "done"
                for dependency_id in task.dependencies
            )
            if blocked:
                task.status = "failed"
                task.error = "Dependency failed"
                failed += 1
                print(f"[SCHEDULER] Failed {task.id}")
                break

            if index > 0:
                time.sleep(1)

            if self._run_task(task):
                completed += 1
            else:
                failed += 1
                break

        return {
            "success": failed == 0,
            "completed": completed,
            "failed": failed,
        }

    def _run_task(self, task):
        max_retries = 2

        for attempt in range(max_retries + 1):
            if attempt == 0:
                print(f"[SCHEDULER] Running task {task.id}")
            else:
                print(f"[SCHEDULER] Retry {task.id}")

            task.status = "running"
            task.error = None

            try:
                task.result = task.func()
                task.status = "done"
                return True
            except Exception as error:
                task.status = "failed"
                task.error = str(error)

        print(f"[SCHEDULER] Failed {task.id}")
        return False
