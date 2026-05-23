from __future__ import annotations

from typing import Any

from .runtime_context import SCHEMA_VERSION, RuntimeContext


class CausalEngine:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context

    def identify(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        for event in events:
            signals = event.get("signals", {})
            if (
                signals.get("generic_route_priority")
                and signals.get("traffic_capture")
                and signals.get("intended_route_bypassed")
                and signals.get("wrong_middleware_chain")
            ):
                rules = self.context.load_json(
                    self.context.pattern_root
                    / "routing_priority"
                    / "3_analysis"
                    / "causal_rules.json"
                )
                return {
                    "schema_version": SCHEMA_VERSION,
                    "cause": "routing_priority",
                    "confidence": rules.get("confidence", 0.87),
                    "evidence": [
                        "generic_route_priority",
                        "traffic_capture",
                        "intended_route_bypassed",
                        "wrong_middleware_chain",
                    ],
                    "learned_patterns": signals.get("learned_patterns", []),
                }
            if (
                signals.get("dependency_unreachable")
                and signals.get("failed_healthcheck")
                and signals.get("degraded_service_health")
            ):
                rules = self.context.load_json(
                    self.context.pattern_root
                    / "service_health"
                    / "3_analysis"
                    / "causal_rules.json"
                )
                return {
                    "schema_version": SCHEMA_VERSION,
                    "cause": "service_health",
                    "confidence": rules.get("confidence", 0.88),
                    "evidence": [
                        "dependency_unreachable",
                        "failed_healthcheck",
                        "degraded_service_health",
                    ],
                    "learned_patterns": signals.get("learned_patterns", []),
                }
            if signals.get("memory_pressure") and signals.get("leak_growth", True):
                rules = self.context.load_json(
                    self.context.pattern_root
                    / "resource_exhaustion"
                    / "3_analysis"
                    / "causal_rules.json"
                )
                return {
                    "schema_version": SCHEMA_VERSION,
                    "cause": "resource_exhaustion",
                    "confidence": rules.get("confidence", 0.86),
                    "evidence": ["memory_pressure", "leak_growth"],
                }
        return {
            "schema_version": SCHEMA_VERSION,
            "cause": "unknown",
            "confidence": 0.0,
            "evidence": [],
        }
