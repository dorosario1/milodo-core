from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports" / "soak"
MEMORY_DIR = ROOT / "memory"


def load_dashboard_data() -> dict[str, Any]:
    memory = _read_json(MEMORY_DIR / "causal_memory.json", {})
    ecommerce = _read_json(MEMORY_DIR / "ecommerce_patterns.json", {"patterns": []})
    ui = _read_json(MEMORY_DIR / "ui_fixes.json", {"patterns": []})
    latest_state = _read_json(REPORTS_DIR / "latest_state.json", {})
    long_term = _read_json(REPORTS_DIR / "long_term_report.json", {})
    snapshots = _recent_snapshots()
    return {
        "soak": {
            "latest_state": latest_state,
            "long_term": long_term,
            "recent_reports": _recent_reports(),
        },
        "benchmark": {
            "strategy_scores": memory.get("strategy_scores", {}),
            "runtime_compatibility": memory.get("runtime_compatibility", {}),
            "stability_scores": memory.get("stability_scores", {}),
            "pattern_frequency": memory.get("pattern_frequency", {}),
        },
        "transferability": _transfer_scores(memory),
        "memory": {
            "records": len(memory.get("records", [])),
            "executions": len(memory.get("executions", [])),
            "rollback_history": len(memory.get("rollback_history", [])),
            "stable": not long_term.get("corruption_detected", False),
        },
        "knowledge": {
            "ecommerce_patterns": ecommerce.get("patterns", []),
            "ui_fixes": ui.get("patterns", []),
        },
        "snapshots": snapshots,
    }


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def _recent_reports(limit: int = 5) -> list[dict[str, Any]]:
    reports = sorted(REPORTS_DIR.glob("soak_report_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [{"name": path.name, "data": _read_json(path, {})} for path in reports[:limit]]


def _recent_snapshots(limit: int = 5) -> list[dict[str, Any]]:
    snapshot_dir = REPORTS_DIR / "snapshots"
    snapshots = sorted(snapshot_dir.glob("runtime_snapshot_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [{"name": path.name, "data": _read_json(path, {})} for path in snapshots[:limit]]


def _transfer_scores(memory: dict[str, Any]) -> list[dict[str, Any]]:
    scores = []
    runtime_compatibility = memory.get("runtime_compatibility", {})
    strategy_scores = memory.get("strategy_scores", {})
    for pattern, runtimes in runtime_compatibility.items():
        for runtime, stats in runtimes.items():
            total = stats.get("total", 0)
            runtime_score = stats.get("success", 0) / total if total else 0.0
            best_strategy = _best_strategy(strategy_scores.get(pattern, {}))
            scores.append(
                {
                    "pattern": pattern,
                    "runtime": runtime,
                    "runtime_success": round(runtime_score, 4),
                    "best_strategy": best_strategy,
                }
            )
    return sorted(scores, key=lambda item: item["runtime_success"], reverse=True)


def _best_strategy(strategies: dict[str, Any]) -> str | None:
    if not strategies:
        return None
    ranked = sorted(
        strategies.items(),
        key=lambda item: (
            item[1].get("success", 0) / item[1].get("total", 1),
            item[1].get("stable", 0) / item[1].get("total", 1),
            item[1].get("total", 0),
        ),
        reverse=True,
    )
    return ranked[0][0]

