from __future__ import annotations

from typing import Any


def match(observations: list[dict[str, Any]]) -> bool:
    for observation in observations:
        signals = observation.get("signals", {})
        if (
            signals.get("generic_route_priority")
            and signals.get("traffic_capture")
            and signals.get("intended_route_bypassed")
            and signals.get("wrong_middleware_chain")
        ):
            return True
    return False


def extract_features(observations: list[dict[str, Any]]) -> dict[str, Any]:
    for observation in observations:
        signals = observation.get("signals", {})
        if (
            signals.get("generic_route_priority")
            and signals.get("traffic_capture")
            and signals.get("intended_route_bypassed")
            and signals.get("wrong_middleware_chain")
        ):
            return {
                "evidence": [
                    "generic_route_priority",
                    "traffic_capture",
                    "intended_route_bypassed",
                    "wrong_middleware_chain",
                ],
                "learned_patterns": signals.get("learned_patterns", []),
            }
    return {"evidence": []}
