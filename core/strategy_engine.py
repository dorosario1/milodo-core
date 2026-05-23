from __future__ import annotations

from typing import Any

from memory.causal_memory import CausalMemory

from .runtime_context import SCHEMA_VERSION, RuntimeContext


class StrategyEngine:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context

    def apply(self, causal_result: dict[str, Any]) -> dict[str, Any]:
        cause = causal_result.get("cause")
        if cause not in {"resource_exhaustion", "service_health", "routing_priority"}:
            return {
                "schema_version": SCHEMA_VERSION,
                "strategy": "noop",
                "applied": False,
                "rollback_available": False,
            }
        strategies = self.context.load_json(
            self.context.pattern_root
            / cause
            / "1_fix"
            / "strategies.json"
        )
        preferred = CausalMemory().get_best_strategy(cause, self.context.runtime)
        strategy = next(
            (
                candidate
                for candidate in strategies["strategies"]
                if candidate["name"] == preferred
            ),
            strategies["strategies"][0],
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "pattern": cause,
            "strategy": strategy["name"],
            "applied": True,
            "actions": strategy["actions"],
            "rollback_strategy": strategy["rollback_strategy"],
            "rollback_available": True,
        }
