from __future__ import annotations

from typing import Any


def match(observations: list[dict[str, Any]]) -> bool:
    for observation in observations:
        signals = observation.get("signals", {})
        if (
            signals.get("dependency_unreachable")
            and signals.get("failed_healthcheck")
            and signals.get("degraded_service_health")
        ):
            return True
    return False


def extract_features(observations: list[dict[str, Any]]) -> dict[str, Any]:
    for observation in observations:
        signals = observation.get("signals", {})
        if (
            signals.get("dependency_unreachable")
            and signals.get("failed_healthcheck")
            and signals.get("degraded_service_health")
        ):
            return {
                "evidence": [
                    "dependency_unreachable",
                    "failed_healthcheck",
                    "degraded_service_health",
                ],
                "learned_patterns": signals.get("learned_patterns", []),
            }
    return {"evidence": []}
