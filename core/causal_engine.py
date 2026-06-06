from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .causal_memory import CausalMemory
from .pattern_registry import evaluate_patterns, load_patterns
from .runtime_context import RuntimeContext


class CausalEngine:
    def __init__(self, context: RuntimeContext) -> None:
        self.context = context
        self.registry = load_patterns(context)
        self.last_event_type = None
        self.last_runtime = None
        self.last_timestamp = None

    def identify(self, events: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | None:
        if isinstance(events, list) and all("event_type" in event for event in events):
            for event in events:
                self.last_event_type = event.get("event_type")
                self.last_runtime = event.get("runtime", self.context.runtime)
                self.last_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                CausalMemory().remember_unknown({
                    "features": {"signals": [self.last_event_type], "signal_frequency": {self.last_event_type: 1}},
                    "source": "causal_engine_event",
                    "timestamp": self.last_timestamp,
                }, self.last_runtime)
            return None
        if isinstance(events, dict):
            return evaluate_patterns([events], self.registry, runtime_type=self.context.runtime)
        return evaluate_patterns(events, self.registry, runtime_type=self.context.runtime)
