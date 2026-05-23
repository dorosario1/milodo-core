from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memory.causal_memory import CausalMemory


SCHEMA_VERSION = "1.0"
ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT / "memory"


MEMORY_FILES = {
    "ecommerce": MEMORY_DIR / "ecommerce_patterns.json",
    "ui": MEMORY_DIR / "ui_fixes.json",
    "conversion": MEMORY_DIR / "conversion_patterns.json",
    "branding": MEMORY_DIR / "branding_patterns.json",
}


def capture_fix_pattern(
    pattern_id: str,
    problem: str,
    recommended_fix: str,
    domain: str = "ui",
    signals: list[str] | None = None,
    source_project: str = "DofitPro",
    success: bool = True,
) -> dict[str, Any]:
    path = MEMORY_FILES.get(domain, MEMORY_FILES["ui"])
    data = _read(path)
    pattern = _find(data, pattern_id)
    if not pattern:
        pattern = {
            "id": pattern_id,
            "domain": domain,
            "problem": problem,
            "signals": signals or [problem],
            "recommended_fix": recommended_fix,
            "source_project": source_project,
            "success_count": 0,
            "failure_count": 0,
            "confidence": 0.0,
        }
        data["patterns"].append(pattern)
    pattern["success_count"] += int(success)
    pattern["failure_count"] += int(not success)
    pattern["confidence"] = _confidence(pattern)
    _write(path, data)
    CausalMemory().persist_execution(_causal_record(pattern, success))
    return pattern


def detect_repeated_success(domain: str | None = None, min_success: int = 2) -> list[dict[str, Any]]:
    patterns = _all_patterns(domain)
    return [
        pattern
        for pattern in patterns
        if pattern.get("success_count", 0) >= min_success
        and pattern.get("success_count", 0) > pattern.get("failure_count", 0)
    ]


def recommend_known_fix(input_text: str, domain: str | None = None) -> dict[str, Any]:
    text = input_text.lower()
    candidates = []
    for pattern in _all_patterns(domain):
        signals = [pattern.get("problem", ""), *pattern.get("signals", [])]
        matches = sum(1 for signal in signals if signal.lower() in text)
        token_matches = sum(
            1
            for signal in signals
            for token in signal.lower().split()
            if len(token) > 3 and token in text
        )
        score = matches * 2 + token_matches
        if score:
            candidates.append((score, pattern))
    if not candidates:
        return {
            "schema_version": SCHEMA_VERSION,
            "known_pattern": None,
            "recommended_fix": None,
            "confidence": 0.0,
            "source_project": None,
        }
    _, best = sorted(candidates, key=lambda item: (item[0], item[1].get("confidence", 0)), reverse=True)[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "known_pattern": best["id"],
        "recommended_fix": best["recommended_fix"],
        "confidence": best.get("confidence", 0.0),
        "source_project": best.get("source_project"),
    }


def _all_patterns(domain: str | None = None) -> list[dict[str, Any]]:
    paths = [MEMORY_FILES[domain]] if domain in MEMORY_FILES else MEMORY_FILES.values()
    patterns = []
    for path in paths:
        patterns.extend(_read(path).get("patterns", []))
    return patterns


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "patterns": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "schema_version" not in data:
        raise ValueError(f"Missing schema_version in {path}")
    data.setdefault("patterns", [])
    return data


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _find(data: dict[str, Any], pattern_id: str) -> dict[str, Any] | None:
    return next((pattern for pattern in data["patterns"] if pattern.get("id") == pattern_id), None)


def _confidence(pattern: dict[str, Any]) -> float:
    success = pattern.get("success_count", 0)
    failure = pattern.get("failure_count", 0)
    return round((success + 1) / (success + failure + 2), 2)


def _causal_record(pattern: dict[str, Any], success: bool) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime": "knowledge",
        "incident": "captured",
        "causal_engine": {"cause": pattern["id"]},
        "strategy_engine": {
            "pattern": pattern["id"],
            "strategy": pattern["recommended_fix"],
            "applied": success,
            "rollback_strategy": {"name": "do_not_reuse_pattern", "available": True},
        },
        "validation_engine": {"stable": success, "rollback_available": True},
    }

