"""
MILODO DAG Engine V1

Minimal, in-memory DAG execution engine.

Design goals:
- No external dependencies
- Deterministic topological execution
- Clear failure handling
- Small API surface for future AI planner and scheduler integration
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional


VALID_STATUSES = {"pending", "running", "done", "failed"}


class Task:
    """A single executable unit in a DAG."""

    def __init__(
        self,
        id: str,
        func: Callable[[], Any],
        dependencies: Optional[List[str]] = None,
    ) -> None:
        if not id or not isinstance(id, str):
            raise ValueError("Task id must be a non-empty string")
        if not callable(func):
            raise TypeError("Task func must be callable")

        self.id = id
        self.func = func
        self.dependencies = list(dependencies or [])
        self.status = "pending"
        self.result: Any = None
        self.error: Optional[str] = None

    def reset(self) -> None:
        self.status = "pending"
        self.result = None
        self.error = None


class DAG:
    """Deterministic directed acyclic graph executor."""

    def __init__(
        self,
        tasks: Optional[Iterable[Task]] = None,
        continue_on_failure: bool = False,
    ) -> None:
        self.tasks: Dict[str, Task] = {}
        self.continue_on_failure = continue_on_failure

        for task in tasks or []:
            self.add_task(task)

    def add_task(self, task: Task) -> None:
        if not isinstance(task, Task):
            raise TypeError("DAG.add_task expects a Task instance")
        if task.id in self.tasks:
            raise ValueError(f"Duplicate task id: {task.id}")

        self.tasks[task.id] = task

    def _validate_dependencies(self) -> None:
        for task in self.tasks.values():
            for dependency_id in task.dependencies:
                if dependency_id not in self.tasks:
                    raise Exception(f"Missing dependency: {task.id} depends on {dependency_id}")

    def _topological_order(self) -> List[Task]:
        self._validate_dependencies()

        ordered: List[Task] = []
        visiting = set()
        visited = set()

        def visit(task: Task) -> None:
            if task.id in visited:
                return
            if task.id in visiting:
                raise Exception(f"Circular dependency detected at task: {task.id}")

            visiting.add(task.id)
            for dependency_id in task.dependencies:
                visit(self.tasks[dependency_id])
            visiting.remove(task.id)
            visited.add(task.id)
            ordered.append(task)

        for task in self.tasks.values():
            visit(task)

        return ordered

    def _reset_tasks(self) -> None:
        for task in self.tasks.values():
            task.reset()

    def _summary(self) -> Dict[str, Any]:
        completed = sum(1 for task in self.tasks.values() if task.status == "done")
        failed = sum(1 for task in self.tasks.values() if task.status == "failed")
        results = {
            task.id: task.result
            for task in self.tasks.values()
            if task.status == "done"
        }

        return {
            "success": failed == 0,
            "completed": completed,
            "failed": failed,
            "results": results,
        }

    def run(self) -> Dict[str, Any]:
        self._reset_tasks()
        ordered_tasks = self._topological_order()

        for task in ordered_tasks:
            blocked = any(self.tasks[dependency_id].status != "done" for dependency_id in task.dependencies)
            if blocked:
                task.status = "failed"
                task.error = "Dependency failed"
                print(f"[DAG] Failed task {task.id}")
                if not self.continue_on_failure:
                    break
                continue

            print(f"[DAG] Running task {task.id}")
            task.status = "running"

            try:
                task.result = task.func()
                task.status = "done"
                print(f"[DAG] Done task {task.id}")
            except Exception as exc:
                task.status = "failed"
                task.error = str(exc)
                print(f"[DAG] Failed task {task.id}")
                if not self.continue_on_failure:
                    break

        return self._summary()


if __name__ == "__main__":
    tasks = [
        Task("A", lambda: print("A")),
        Task("B", lambda: print("B"), dependencies=["A"]),
        Task("C", lambda: print("C"), dependencies=["B"]),
    ]

    dag = DAG(tasks)
    print(dag.run())
