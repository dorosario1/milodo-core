from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.causal_memory import CausalMemory

from .causal_benchmark import CausalBenchmark
from .runtime_context import SCHEMA_VERSION
from .soak_persistence import DEFAULT_REPORT_DIR, save_soak_report


SNAPSHOT_DIR = DEFAULT_REPORT_DIR / "snapshots"


def save_runtime_snapshot(
    reports_dir: Path | None = None,
    memory: CausalMemory | None = None,
    patterns: list[str] | None = None,
) -> Path:
    target_dir = (reports_dir or DEFAULT_REPORT_DIR) / "snapshots"
    target_dir.mkdir(parents=True, exist_ok=True)
    memory = memory or CausalMemory()
    data = memory.read()
    benchmark = CausalBenchmark(memory)
    selected_patterns = patterns or sorted(data.get("pattern_frequency", {}))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "memory": {
            "path": str(memory.path),
            "bytes": memory.path.stat().st_size if memory.path.exists() else 0,
            "records": len(data.get("records", [])),
            "executions": len(data.get("executions", [])),
            "rollback_history": len(data.get("rollback_history", [])),
            "corruption_detected": not _json_valid(memory.path),
        },
        "patterns": {
            pattern: benchmark.benchmark_pattern(pattern)
            for pattern in selected_patterns
        },
        "strategies": {
            pattern: memory.get_best_strategy(pattern, "docker")
            for pattern in selected_patterns
        },
    }
    path = target_dir / f"runtime_snapshot_{_timestamp()}.json"
    _atomic_write(path, payload)
    return path


def compare_snapshot_drift(
    baseline_snapshot: Path,
    current_snapshot: Path,
    memory_growth_ratio: float = 0.5,
    transfer_drop_threshold: float = 0.1,
) -> dict[str, Any]:
    baseline = _read_json(baseline_snapshot)
    current = _read_json(current_snapshot)
    baseline_bytes = baseline["memory"].get("bytes", 0)
    current_bytes = current["memory"].get("bytes", 0)
    growth_ratio = (current_bytes - baseline_bytes) / max(baseline_bytes, 1)
    transfer_drop = _max_transfer_drop(baseline, current)
    strategy_changed = _strategy_changed(baseline, current)
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_snapshot": baseline_snapshot.name,
        "current_snapshot": current_snapshot.name,
        "memory_growth_ratio": round(max(growth_ratio, 0.0), 4),
        "memory_drift_detected": baseline_bytes > 0 and growth_ratio > memory_growth_ratio,
        "transfer_drop": round(transfer_drop, 4),
        "benchmark_regression": transfer_drop > transfer_drop_threshold,
        "strategy_instability": strategy_changed,
        "corruption_detected": bool(current["memory"].get("corruption_detected")),
    }


def detect_long_term_regression(snapshots_dir: Path | None = None) -> dict[str, Any]:
    target_dir = snapshots_dir or SNAPSHOT_DIR
    snapshots = sorted(target_dir.glob("runtime_snapshot_*.json"))
    if len(snapshots) < 2:
        return {
            "schema_version": SCHEMA_VERSION,
            "regression_detected": False,
            "reason": "not enough snapshots",
            "snapshot_count": len(snapshots),
        }
    drift = compare_snapshot_drift(snapshots[0], snapshots[-1])
    regression = any(
        [
            drift["memory_drift_detected"],
            drift["benchmark_regression"],
            drift["strategy_instability"],
            drift["corruption_detected"],
        ]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "regression_detected": regression,
        "snapshot_count": len(snapshots),
        "drift": drift,
    }


def generate_long_term_report(reports_dir: Path | None = None) -> dict[str, Any]:
    target_dir = reports_dir or DEFAULT_REPORT_DIR
    snapshot_dir = target_dir / "snapshots"
    snapshots = sorted(snapshot_dir.glob("runtime_snapshot_*.json"))
    regression = detect_long_term_regression(snapshot_dir)
    latest = _read_json(snapshots[-1]) if snapshots else None
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshots": len(snapshots),
        "stable": not regression.get("regression_detected", False),
        "memory_drift_detected": regression.get("drift", {}).get("memory_drift_detected", False),
        "benchmark_regression": regression.get("drift", {}).get("benchmark_regression", False),
        "strategy_instability": regression.get("drift", {}).get("strategy_instability", False),
        "corruption_detected": regression.get("drift", {}).get("corruption_detected", False),
        "latest_snapshot": latest,
        "regression": regression,
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(target_dir / "long_term_report.json", report)
    save_soak_report(report, target_dir)
    return report


def _max_transfer_drop(baseline: dict[str, Any], current: dict[str, Any]) -> float:
    drops = []
    for pattern, baseline_data in baseline.get("patterns", {}).items():
        current_data = current.get("patterns", {}).get(pattern, {})
        drops.append(
            baseline_data.get("transferability_score", 0.0)
            - current_data.get("transferability_score", 0.0)
        )
    return max(drops or [0.0])


def _strategy_changed(baseline: dict[str, Any], current: dict[str, Any]) -> bool:
    for key, strategy in baseline.get("strategies", {}).items():
        if strategy and current.get("strategies", {}).get(key) != strategy:
            return True
    return False


def _json_valid(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except json.JSONDecodeError:
        return False


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
