from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_context import SCHEMA_VERSION


DEFAULT_REPORT_DIR = Path(__file__).resolve().parents[1] / "reports" / "soak"


def save_soak_report(report: dict[str, Any], reports_dir: Path | None = None) -> Path:
    target_dir = reports_dir or DEFAULT_REPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "report": report,
    }
    report_path = target_dir / f"soak_report_{timestamp}.json"
    _atomic_write(report_path, payload)
    _atomic_write(
        target_dir / "latest_state.json",
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": payload["saved_at"],
            "last_report": report_path.name,
            "cycles": report.get("cycles", 0),
            "stable": report.get("stable", False),
            "interrupted": report.get("interrupted", False),
            "history": {
                "memory_growth_detected": report.get("memory_growth_detected", False),
                "strategy_regression": report.get("strategy_regression", False),
                "transfer_consistency": report.get("transfer_consistency", 0.0),
                "corruption_detected": report.get("corruption_detected", False),
            },
        },
    )
    return report_path


def rotate_old_reports(reports_dir: Path | None = None, keep: int = 24) -> list[str]:
    target_dir = reports_dir or DEFAULT_REPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    reports = sorted(
        target_dir.glob("soak_report_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    rotated = []
    for report in reports[max(keep, 0):]:
        archive = report.with_suffix(report.suffix + ".rotated")
        os.replace(report, archive)
        rotated.append(archive.name)
    return rotated


def resume_previous_soak(reports_dir: Path | None = None) -> dict[str, Any]:
    target_dir = reports_dir or DEFAULT_REPORT_DIR
    state_path = target_dir / "latest_state.json"
    if not state_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "resumable": False,
            "next_cycle": 1,
            "last_report": None,
        }
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return {
        "schema_version": SCHEMA_VERSION,
        "resumable": True,
        "next_cycle": int(state.get("cycles", 0)) + 1,
        "last_report": state.get("last_report"),
        "stable": state.get("stable", False),
        "interrupted": state.get("interrupted", False),
        "history": state.get("history", {}),
    }


def graceful_shutdown(runner: Any, partial_report: dict[str, Any] | None = None, reports_dir: Path | None = None) -> dict[str, Any]:
    if hasattr(runner, "request_stop"):
        runner.request_stop()
    report = dict(partial_report or {})
    report.setdefault("schema_version", SCHEMA_VERSION)
    report["interrupted"] = True
    report["shutdown_at"] = datetime.now(timezone.utc).isoformat()
    path = save_soak_report(report, reports_dir)
    return {
        "schema_version": SCHEMA_VERSION,
        "stopped": True,
        "report": path.name,
        "interrupted": True,
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
