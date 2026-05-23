from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from core.runtime_context import SCHEMA_VERSION


class CausalMemory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parent / "causal_memory.json"
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._lock_handle = None
        self._lock_acquired = False

    def append(self, record: dict[str, Any]) -> None:
        self.persist_execution(record)

    def persist_execution(self, record: dict[str, Any]) -> None:
        self.acquire_lock()
        try:
            current = self._read_unlocked()
            execution = self._normalize_execution(record)
            current["records"].append(record)
            current["executions"].append(execution)
            self._update_aggregates(current, execution)
            self.atomic_write(current)
        finally:
            self.release_lock()

    def read(self) -> dict[str, Any]:
        self.acquire_lock()
        try:
            return self._read_unlocked()
        finally:
            self.release_lock()

    def acquire_lock(self, timeout: float = 5.0, poll_interval: float = 0.05) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + timeout
        self._lock_handle = self.lock_path.open("a+b")
        while True:
            try:
                self._platform_lock()
                self._lock_acquired = True
                return True
            except OSError:
                if time.monotonic() >= deadline:
                    self._lock_acquired = False
                    return False
                time.sleep(poll_interval)

    def release_lock(self) -> None:
        if not self._lock_handle:
            return
        try:
            if self._lock_acquired:
                self._platform_unlock()
        finally:
            self._lock_handle.close()
            self._lock_handle = None
            self._lock_acquired = False

    def atomic_write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + f".tmp.{os.getpid()}")
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temp_path, self.path)

    def recover_if_corrupted(self) -> bool:
        if not self.path.exists():
            return False
        try:
            json.loads(self.path.read_text(encoding="utf-8"))
            return False
        except json.JSONDecodeError:
            corrupt_path = self.path.with_suffix(
                self.path.suffix + f".corrupt.{int(time.time())}.{os.getpid()}"
            )
            os.replace(self.path, corrupt_path)
            self.atomic_write(self._empty())
            return True

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        self.recover_if_corrupted()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._empty()
        if "schema_version" not in data:
            raise ValueError(f"Missing schema_version in {self.path}")
        data.setdefault("records", [])
        data.setdefault("executions", [])
        data.setdefault("strategy_scores", {})
        data.setdefault("stability_scores", {})
        data.setdefault("pattern_frequency", {})
        data.setdefault("runtime_compatibility", {})
        data.setdefault("rollback_history", [])
        return data

    def get_strategy_success_rate(self, problem_class: str, strategy: str) -> float:
        data = self.read()
        stats = data["strategy_scores"].get(problem_class, {}).get(strategy)
        if not stats or not stats.get("total"):
            return 0.0
        return stats["success"] / stats["total"]

    def get_pattern_frequency(self, problem_class: str) -> int:
        return int(self.read()["pattern_frequency"].get(problem_class, 0))

    def get_runtime_success_rate(self, problem_class: str, runtime: str) -> float:
        data = self.read()
        stats = data["runtime_compatibility"].get(problem_class, {}).get(runtime)
        if not stats or not stats.get("total"):
            return 0.0
        return stats["success"] / stats["total"]

    def get_best_strategy(self, problem_class: str, runtime: str) -> str | None:
        data = self.read()
        strategies = data["strategy_scores"].get(problem_class, {})
        if not strategies:
            return None
        runtime_rate = self.get_runtime_success_rate(problem_class, runtime)
        ranked = sorted(
            strategies.items(),
            key=lambda item: (
                item[1]["success"] / item[1]["total"] if item[1].get("total") else 0.0,
                item[1].get("stable", 0) / item[1]["total"] if item[1].get("total") else 0.0,
                runtime_rate,
                item[1].get("total", 0),
            ),
            reverse=True,
        )
        return ranked[0][0] if ranked else None

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "records": [],
            "executions": [],
            "strategy_scores": {},
            "stability_scores": {},
            "pattern_frequency": {},
            "runtime_compatibility": {},
            "rollback_history": [],
        }

    def _normalize_execution(self, record: dict[str, Any]) -> dict[str, Any]:
        causal = record.get("causal_engine", {})
        strategy = record.get("strategy_engine", {})
        validation = record.get("validation_engine", {})
        problem_class = causal.get("cause") or strategy.get("pattern") or "unknown"
        runtime = record.get("runtime", "unknown")
        return {
            "schema_version": SCHEMA_VERSION,
            "problem_class": problem_class,
            "runtime": runtime,
            "strategy": strategy.get("strategy", "unknown"),
            "success": bool(strategy.get("applied") and validation.get("stable")),
            "stable": bool(validation.get("stable")),
            "rollback_available": bool(validation.get("rollback_available")),
            "rollback_strategy": strategy.get("rollback_strategy"),
        }

    def _update_aggregates(self, data: dict[str, Any], execution: dict[str, Any]) -> None:
        problem_class = execution["problem_class"]
        strategy = execution["strategy"]
        runtime = execution["runtime"]
        data["pattern_frequency"][problem_class] = data["pattern_frequency"].get(problem_class, 0) + 1

        strategy_bucket = data["strategy_scores"].setdefault(problem_class, {}).setdefault(
            strategy,
            {"total": 0, "success": 0, "stable": 0},
        )
        self._bump(strategy_bucket, execution)

        stability_bucket = data["stability_scores"].setdefault(
            problem_class,
            {"total": 0, "success": 0, "stable": 0},
        )
        self._bump(stability_bucket, execution)

        runtime_bucket = data["runtime_compatibility"].setdefault(problem_class, {}).setdefault(
            runtime,
            {"total": 0, "success": 0, "stable": 0},
        )
        self._bump(runtime_bucket, execution)

        if execution.get("rollback_available"):
            data["rollback_history"].append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "problem_class": problem_class,
                    "runtime": runtime,
                    "strategy": strategy,
                    "rollback_strategy": execution.get("rollback_strategy"),
                }
            )

    def _bump(self, bucket: dict[str, int], execution: dict[str, Any]) -> None:
        bucket["total"] += 1
        bucket["success"] += int(execution["success"])
        bucket["stable"] += int(execution["stable"])

    def _platform_lock(self) -> None:
        if os.name == "nt":
            import msvcrt

            self._lock_handle.seek(0)
            msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _platform_unlock(self) -> None:
        if os.name == "nt":
            import msvcrt

            self._lock_handle.seek(0)
            msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
