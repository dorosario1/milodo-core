from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from memory.causal_memory import CausalMemory

from .causal_benchmark import CausalBenchmark
from .causal_engine import CausalEngine
from .event_pipeline import EventPipeline
from .runtime_context import SCHEMA_VERSION, RuntimeContext
from .runtime_transfer_validator import RuntimeTransferValidator
from .strategy_engine import StrategyEngine
from .validation_engine import ValidationEngine


class SoakRunner:
    def __init__(
        self,
        patterns: list[str] | None = None,
        runtimes: list[str] | None = None,
        memory: CausalMemory | None = None,
        root: Path | None = None,
    ) -> None:
        self.patterns = patterns or ["resource_exhaustion", "service_health", "routing_priority"]
        self.runtimes = runtimes or ["docker"]
        self.memory = memory or CausalMemory()
        self.root = root or Path(__file__).resolve().parents[1]
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True

    def run_soak_test(self, interval: float = 0.0, max_cycles: int = 1) -> dict[str, Any]:
        baseline_size = self._memory_size()
        strategy_baseline = self.monitor_strategy_stability()
        cycle_results = []

        for cycle in range(max_cycles):
            if self.stop_requested:
                break
            for pattern in self.patterns:
                for runtime in self.runtimes:
                    if self.stop_requested:
                        break
                    cycle_results.append(self._run_once(pattern, runtime, cycle + 1))
            if interval > 0 and cycle < max_cycles - 1 and not self.stop_requested:
                time.sleep(interval)

        memory_growth = self.monitor_memory_growth(baseline_size)
        strategy_after = self.monitor_strategy_stability()
        transfer_consistency = self.monitor_transfer_consistency()
        return self.generate_soak_report(
            cycles=len({item["cycle"] for item in cycle_results}),
            cycle_results=cycle_results,
            memory_growth=memory_growth,
            strategy_baseline=strategy_baseline,
            strategy_after=strategy_after,
            transfer_consistency=transfer_consistency,
        )

    def monitor_memory_growth(self, baseline_size: int | None = None, max_growth_ratio: float = 2.0) -> dict[str, Any]:
        current_size = self._memory_size()
        baseline = baseline_size if baseline_size is not None else current_size
        growth = max(current_size - baseline, 0)
        growth_ratio = growth / max(baseline, 1)
        corrupted = not self._memory_json_valid()
        detected = baseline > 0 and growth_ratio > max_growth_ratio
        return {
            "schema_version": SCHEMA_VERSION,
            "baseline_bytes": baseline,
            "current_bytes": current_size,
            "growth_bytes": growth,
            "growth_ratio": round(growth_ratio, 4),
            "memory_growth_detected": detected,
            "corruption_detected": corrupted,
        }

    def monitor_strategy_stability(self) -> dict[str, Any]:
        strategies = {}
        for pattern in self.patterns:
            for runtime in self.runtimes:
                strategies[f"{pattern}:{runtime}"] = self.memory.get_best_strategy(pattern, runtime)
        return {
            "schema_version": SCHEMA_VERSION,
            "strategies": strategies,
        }

    def monitor_transfer_consistency(self) -> float:
        benchmark = CausalBenchmark(
            self.memory,
            RuntimeTransferValidator(self.memory),
        )
        scores = []
        for pattern in self.patterns:
            transfers = benchmark.rank_transferability(pattern)
            scores.extend(item["confidence"] for item in transfers)
        if not scores:
            return 1.0
        return round(sum(scores) / len(scores), 4)

    def generate_soak_report(
        self,
        cycles: int,
        cycle_results: list[dict[str, Any]],
        memory_growth: dict[str, Any],
        strategy_baseline: dict[str, Any],
        strategy_after: dict[str, Any],
        transfer_consistency: float,
    ) -> dict[str, Any]:
        strategy_regression = self._strategy_regression(
            strategy_baseline["strategies"],
            strategy_after["strategies"],
        )
        stable = all(item["stable"] for item in cycle_results)
        return {
            "schema_version": SCHEMA_VERSION,
            "cycles": cycles,
            "stable": stable and not memory_growth["corruption_detected"],
            "memory_growth_detected": memory_growth["memory_growth_detected"],
            "strategy_regression": strategy_regression,
            "transfer_consistency": transfer_consistency,
            "corruption_detected": memory_growth["corruption_detected"],
            "benchmark_consistent": transfer_consistency >= 0.5,
            "runtime_regression": not stable,
            "memory": memory_growth,
            "strategy_stability": strategy_after,
            "results": cycle_results,
        }

    def _run_once(self, pattern: str, runtime: str, cycle: int) -> dict[str, Any]:
        context = RuntimeContext(runtime=runtime, root=self.root)
        events = EventPipeline(context).collect(pattern)
        causal = CausalEngine(context).identify(events)
        strategy = StrategyEngine(context).apply(causal)
        validation = ValidationEngine(context).validate(strategy)
        record = {
            "schema_version": SCHEMA_VERSION,
            "runtime": runtime,
            "incident": "detected" if events else "none",
            "causal_engine": causal,
            "strategy_engine": strategy,
            "validation_engine": validation,
        }
        self.memory.persist_execution(record)
        return {
            "schema_version": SCHEMA_VERSION,
            "cycle": cycle,
            "pattern": pattern,
            "runtime": runtime,
            "strategy": strategy.get("strategy"),
            "stable": bool(validation.get("stable")),
            "rollback_available": bool(validation.get("rollback_available")),
        }

    def _memory_size(self) -> int:
        return self.memory.path.stat().st_size if self.memory.path.exists() else 0

    def _memory_json_valid(self) -> bool:
        if not self.memory.path.exists():
            return True
        try:
            json.loads(self.memory.path.read_text(encoding="utf-8"))
            return True
        except json.JSONDecodeError:
            return False

    def _strategy_regression(self, before: dict[str, Any], after: dict[str, Any]) -> bool:
        for key, strategy in before.items():
            if strategy and after.get(key) != strategy:
                return True
        return False


def run_soak_test(
    patterns: list[str] | None = None,
    runtimes: list[str] | None = None,
    interval: float = 0.0,
    max_cycles: int = 1,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    memory = CausalMemory(memory_path) if memory_path else None
    return SoakRunner(patterns=patterns, runtimes=runtimes, memory=memory).run_soak_test(
        interval=interval,
        max_cycles=max_cycles,
    )
