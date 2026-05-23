from __future__ import annotations

from pathlib import Path
from typing import Any

from memory.causal_memory import CausalMemory

from .runtime_context import SCHEMA_VERSION


class RuntimeTransferValidator:
    def __init__(self, memory: CausalMemory | None = None) -> None:
        self.memory = memory or CausalMemory()

    def compare_runtime_behavior(
        self,
        pattern: str,
        source_runtime: str,
        target_runtime: str,
    ) -> dict[str, Any]:
        executions = self._matching_executions(pattern)
        source = [item for item in executions if item.get("runtime") == source_runtime]
        target = [item for item in executions if item.get("runtime") == target_runtime]
        source_seen = bool(source)
        target_seen = bool(target)
        return {
            "schema_version": SCHEMA_VERSION,
            "pattern": pattern,
            "source_runtime": source_runtime,
            "target_runtime": target_runtime,
            "source_observed": source_seen,
            "target_observed": target_seen,
            "behavior_match": source_seen and target_seen,
            "source_frequency": len(source),
            "target_frequency": len(target),
        }

    def compare_strategy_success(
        self,
        pattern: str,
        source_runtime: str,
        target_runtime: str,
    ) -> dict[str, Any]:
        source_strategy = self.memory.get_best_strategy(pattern, source_runtime)
        target_strategy = self.memory.get_best_strategy(pattern, target_runtime)
        reusable = bool(source_strategy and (target_strategy in {None, source_strategy}))
        return {
            "schema_version": SCHEMA_VERSION,
            "pattern": pattern,
            "source_runtime": source_runtime,
            "target_runtime": target_runtime,
            "source_strategy": source_strategy,
            "target_strategy": target_strategy,
            "strategy_reusable": reusable,
            "source_success_rate": self._strategy_rate(pattern, source_strategy),
            "target_runtime_success_rate": self.memory.get_runtime_success_rate(
                pattern,
                target_runtime,
            ),
        }

    def validate_transferability(
        self,
        pattern: str,
        source_runtime: str,
        target_runtime: str,
    ) -> dict[str, Any]:
        behavior = self.compare_runtime_behavior(pattern, source_runtime, target_runtime)
        strategy = self.compare_strategy_success(pattern, source_runtime, target_runtime)
        confidence = self.compute_transfer_confidence(pattern, source_runtime, target_runtime)
        return {
            "schema_version": SCHEMA_VERSION,
            "pattern": pattern,
            "source_runtime": source_runtime,
            "target_runtime": target_runtime,
            "transferable": confidence >= 0.5 and strategy["strategy_reusable"],
            "confidence": confidence,
            "runtime_compatibility": {
                source_runtime: self.memory.get_runtime_success_rate(pattern, source_runtime),
                target_runtime: self.memory.get_runtime_success_rate(pattern, target_runtime),
            },
            "strategy_reusable": strategy["strategy_reusable"],
            "strategy": strategy["source_strategy"],
            "behavior": behavior,
        }

    def compute_transfer_confidence(
        self,
        pattern: str,
        source_runtime: str,
        target_runtime: str,
    ) -> float:
        behavior = self.compare_runtime_behavior(pattern, source_runtime, target_runtime)
        strategy = self.compare_strategy_success(pattern, source_runtime, target_runtime)
        source_rate = self.memory.get_runtime_success_rate(pattern, source_runtime)
        target_rate = self.memory.get_runtime_success_rate(pattern, target_runtime)
        strategy_rate = strategy["source_success_rate"]
        behavior_score = 1.0 if behavior["behavior_match"] else 0.55 if behavior["source_observed"] else 0.0
        reusable_score = 1.0 if strategy["strategy_reusable"] else 0.0
        confidence = (
            behavior_score * 0.35
            + source_rate * 0.2
            + target_rate * 0.2
            + strategy_rate * 0.15
            + reusable_score * 0.1
        )
        return round(min(max(confidence, 0.0), 1.0), 2)

    def _matching_executions(self, pattern: str) -> list[dict[str, Any]]:
        return [
            execution
            for execution in self.memory.read().get("executions", [])
            if execution.get("problem_class") == pattern
        ]

    def _strategy_rate(self, pattern: str, strategy: str | None) -> float:
        if not strategy:
            return 0.0
        return self.memory.get_strategy_success_rate(pattern, strategy)


def validate_transferability(
    pattern: str,
    source_runtime: str,
    target_runtime: str,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    memory = CausalMemory(memory_path) if memory_path else None
    return RuntimeTransferValidator(memory).validate_transferability(
        pattern,
        source_runtime,
        target_runtime,
    )
