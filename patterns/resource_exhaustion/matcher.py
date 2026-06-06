from __future__ import annotations

from typing import Any


def match(observations: list[dict[str, Any]]) -> bool:
    for observation in observations:
        signals = observation.get("signals", {})
        if signals.get("memory_pressure") and signals.get("leak_growth", True):
            return True
    return False


def extract_features(observations: list[dict[str, Any]]) -> dict[str, Any]:
    return {"evidence": ["memory_pressure", "leak_growth"]}
