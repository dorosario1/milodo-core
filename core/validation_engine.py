from __future__ import annotations

from typing import Any

from .runtime_context import SCHEMA_VERSION, RuntimeContext


class ValidationEngine:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context

    def validate(self, strategy_result: dict[str, Any]) -> dict[str, Any]:
        pattern = strategy_result.get("pattern", "resource_exhaustion")
        validators = self.context.load_json(
            self.context.pattern_root
            / pattern
            / "4_validation"
            / "validators.json"
        )
        stable = bool(strategy_result.get("applied"))
        return {
            "schema_version": SCHEMA_VERSION,
            "stable": stable,
            "checks": validators["checks"],
            "rollback_available": bool(strategy_result.get("rollback_available")),
            "message": "stability confirmed" if stable else "rollback required",
        }
