from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


class CausalInspector:
    def __init__(self, memory_dir: Path = Path(".milodo/causal_memory")) -> None:
        self.memory_dir = memory_dir

    def load_unknowns(self) -> list[dict[str, Any]]:
        return self._load_jsonl(self.memory_dir / "unknown_patterns.jsonl")

    def load_matches(self) -> list[dict[str, Any]]:
        return self._load_jsonl(self.memory_dir / "matches.jsonl")

    def load_near_matches(self) -> list[dict[str, Any]]:
        return self._load_jsonl(self.memory_dir / "near_matches.jsonl")

    def get_top_signals(
        self,
        unknowns: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        signals = Counter()
        for record in unknowns:
            features = record.get("features", {})
            signal_frequency = features.get("signal_frequency", record.get("signal_frequency", {}))
            if signal_frequency:
                signals.update(signal_frequency)
                continue

            record_signals = features.get("signals", record.get("signals", []))
            signals.update(record_signals)
        return signals.most_common(limit)

    def get_pattern_crashes(self, unknowns: list[dict[str, Any]]) -> Counter:
        crashes = Counter()
        for record in unknowns:
            for error in record.get("pattern_errors", []):
                pattern = error.get("pattern", error.get("pattern_id"))
                if pattern:
                    crashes[pattern] += 1
        return crashes

    def get_runtime_distribution(self, records: list[dict[str, Any]]) -> Counter:
        return Counter(record.get("runtime_type", "unknown") for record in records)

    def get_summary(
        self,
        unknowns: list[dict[str, Any]] | None = None,
        matches: list[dict[str, Any]] | None = None,
        near_matches: list[dict[str, Any]] | None = None,
        top_limit: int = 10,
    ) -> dict[str, Any]:
        unknowns = self.load_unknowns() if unknowns is None else unknowns
        matches = self.load_matches() if matches is None else matches
        near_matches = self.load_near_matches() if near_matches is None else near_matches
        all_records = [*unknowns, *matches, *near_matches]
        return {
            "volumes": {
                "unknowns": len(unknowns),
                "matches": len(matches),
                "near_matches": len(near_matches),
            },
            "top_signals": self.get_top_signals(unknowns, top_limit),
            "pattern_crashes": self.get_pattern_crashes(unknowns),
            "runtime_distribution": self.get_runtime_distribution(all_records),
        }

    def print_report(self) -> None:
        summary = self.get_summary()
        volumes = summary["volumes"]
        runtime_distribution = summary["runtime_distribution"]
        runtime_total = sum(runtime_distribution.values())

        print("MILODO Causal Memory Report")
        print("===========================")
        print(f"Unknowns: {volumes['unknowns']}")
        print(f"Matches: {volumes['matches']}")
        print(f"Near matches: {volumes['near_matches']}")
        print("")
        print("Top unknown signals:")
        for signal, count in summary["top_signals"]:
            print(f"- {signal}: {count}")
        print("")
        print("Pattern crashes:")
        for pattern, count in summary["pattern_crashes"].most_common():
            print(f"- {pattern}: {count}")
        print("")
        print("Runtime distribution:")
        for runtime, count in runtime_distribution.most_common():
            percentage = (count / runtime_total * 100) if runtime_total else 0.0
            print(f"- {runtime}: {count} ({percentage:.1f}%)")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        records = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records
