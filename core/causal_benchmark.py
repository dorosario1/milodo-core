from __future__ import annotations

from typing import Any

from memory.causal_memory import CausalMemory

from .runtime_context import SCHEMA_VERSION
from .runtime_transfer_validator import RuntimeTransferValidator


class CausalBenchmark:
    def __init__(
        self,
        memory: CausalMemory | None = None,
        transfer_validator: RuntimeTransferValidator | None = None,
    ) -> None:
        self.memory = memory or CausalMemory()
        self.transfer_validator = transfer_validator or RuntimeTransferValidator(self.memory)

    def benchmark_pattern(self, pattern: str) -> dict[str, Any]:
        runtimes = self.compute_runtime_reliability(pattern)
        strategies = self.benchmark_strategy(pattern)
        transfers = self.rank_transferability(pattern)
        stability = self._stability_score(pattern)
        return {
            "schema_version": SCHEMA_VERSION,
            "pattern": pattern,
            "best_runtime": self._top_key(runtimes),
            "best_strategy": strategies[0]["strategy"] if strategies else None,
            "runtime_reliability": runtimes,
            "transferability_score": transfers[0]["confidence"] if transfers else 0.0,
            "stability_score": stability,
            "strategy_ranking": strategies,
            "transferability_ranking": transfers,
        }

    def benchmark_runtime(self, runtime: str) -> dict[str, Any]:
        data = self.memory.read()
        patterns = data.get("runtime_compatibility", {})
        scores = {
            pattern: self.memory.get_runtime_success_rate(pattern, runtime)
            for pattern, runtimes in patterns.items()
            if runtime in runtimes
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "runtime": runtime,
            "reliability": self._average(scores.values()),
            "pattern_scores": scores,
            "pattern_ranking": self._rank_mapping(scores, "pattern"),
        }

    def benchmark_strategy(self, pattern: str) -> list[dict[str, Any]]:
        strategies = self.memory.read().get("strategy_scores", {}).get(pattern, {})
        ranked = []
        for strategy, stats in strategies.items():
            total = stats.get("total", 0)
            success_rate = stats.get("success", 0) / total if total else 0.0
            stability_rate = stats.get("stable", 0) / total if total else 0.0
            ranked.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "strategy": strategy,
                    "success_rate": round(success_rate, 4),
                    "stability_rate": round(stability_rate, 4),
                    "total": total,
                }
            )
        return sorted(
            ranked,
            key=lambda item: (item["success_rate"], item["stability_rate"], item["total"]),
            reverse=True,
        )

    def rank_transferability(self, pattern: str) -> list[dict[str, Any]]:
        runtimes = sorted(self.memory.read().get("runtime_compatibility", {}).get(pattern, {}))
        pairs = []
        for source in runtimes:
            for target in runtimes:
                if source == target:
                    continue
                result = self.transfer_validator.validate_transferability(pattern, source, target)
                pairs.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "source_runtime": source,
                        "target_runtime": target,
                        "confidence": result["confidence"],
                        "transferable": result["transferable"],
                        "strategy": result["strategy"],
                    }
                )
        return sorted(pairs, key=lambda item: item["confidence"], reverse=True)

    def compute_runtime_reliability(self, pattern: str) -> dict[str, float]:
        runtimes = self.memory.read().get("runtime_compatibility", {}).get(pattern, {})
        return {
            runtime: round(self.memory.get_runtime_success_rate(pattern, runtime), 4)
            for runtime in sorted(runtimes)
        }

    def _stability_score(self, pattern: str) -> float:
        stats = self.memory.read().get("stability_scores", {}).get(pattern, {})
        total = stats.get("total", 0)
        return round(stats.get("stable", 0) / total, 4) if total else 0.0

    def _top_key(self, scores: dict[str, float]) -> str | None:
        if not scores:
            return None
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)[0][0]

    def _average(self, values) -> float:
        values = list(values)
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)

    def _rank_mapping(self, scores: dict[str, float], label: str) -> list[dict[str, Any]]:
        return [
            {"schema_version": SCHEMA_VERSION, label: name, "score": score}
            for name, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]
