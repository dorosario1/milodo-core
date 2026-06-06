from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from uuid import uuid4

from core.causal_inspector import CausalInspector


class CausalInspectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.memory_dir = Path(".milodo") / f"causal_inspector_test_{uuid4().hex}"
        self.inspector = CausalInspector(self.memory_dir)

    def tearDown(self) -> None:
        for path in (
            self.memory_dir / "unknown_patterns.jsonl",
            self.memory_dir / "matches.jsonl",
            self.memory_dir / "near_matches.jsonl",
        ):
            if path.exists():
                path.unlink()
        if self.memory_dir.exists():
            self.memory_dir.rmdir()

    def test_load_unknowns_empty_dir(self):
        self.assertEqual(self.inspector.load_unknowns(), [])

    def test_load_unknowns_with_records(self):
        records = [
            {"pattern_id": "unknown", "runtime_type": "docker"},
            {"pattern_id": "unknown", "runtime_type": "kubernetes"},
        ]
        self._write_jsonl("unknown_patterns.jsonl", records)

        self.assertEqual(self.inspector.load_unknowns(), records)

    def test_load_unknowns_handles_malformed_json(self):
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path = self.memory_dir / "unknown_patterns.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pattern_id": "unknown"}) + "\n")
            handle.write("{not-json\n")
            handle.write("\n")
            handle.write(json.dumps({"pattern_id": "unknown", "runtime_type": "docker"}) + "\n")

        records = self.inspector.load_unknowns()

        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["runtime_type"], "docker")

    def test_get_top_signals_with_features_format(self):
        unknowns = [
            {"features": {"signals": ["latency_spike", "dns_flap"]}},
            {"features": {"signals": ["latency_spike"]}},
        ]

        self.assertEqual(
            self.inspector.get_top_signals(unknowns),
            [("latency_spike", 2), ("dns_flap", 1)],
        )

    def test_get_top_signals_with_direct_signals(self):
        unknowns = [
            {"signals": ["latency_spike", "dns_flap"]},
            {"signals": ["dns_flap"]},
        ]

        self.assertEqual(
            self.inspector.get_top_signals(unknowns),
            [("dns_flap", 2), ("latency_spike", 1)],
        )

    def test_get_top_signals_with_frequency(self):
        unknowns = [
            {
                "features": {
                    "signals": ["ignored_when_frequency_exists"],
                    "signal_frequency": {"latency_spike": 3},
                }
            },
            {"signal_frequency": {"dns_flap": 2}},
        ]

        self.assertEqual(
            self.inspector.get_top_signals(unknowns),
            [("latency_spike", 3), ("dns_flap", 2)],
        )

    def test_get_pattern_crashes(self):
        unknowns = [
            {"pattern_errors": [{"pattern": "service_health"}]},
            {"pattern_errors": [{"pattern_id": "routing_priority"}]},
            {"pattern_errors": [{"pattern_id": "service_health"}]},
        ]

        crashes = self.inspector.get_pattern_crashes(unknowns)

        self.assertEqual(crashes["service_health"], 2)
        self.assertEqual(crashes["routing_priority"], 1)

    def test_get_runtime_distribution(self):
        records = [
            {"runtime_type": "docker"},
            {"runtime_type": "docker"},
            {"runtime_type": "kubernetes"},
            {},
        ]

        distribution = self.inspector.get_runtime_distribution(records)

        self.assertEqual(distribution["docker"], 2)
        self.assertEqual(distribution["kubernetes"], 1)
        self.assertEqual(distribution["unknown"], 1)

    def test_print_report_runs_without_error(self):
        self._write_jsonl(
            "unknown_patterns.jsonl",
            [{"features": {"signals": ["latency_spike"]}, "runtime_type": "docker"}],
        )
        self._write_jsonl("matches.jsonl", [{"pattern_id": "service_health", "runtime_type": "docker"}])

        with contextlib.redirect_stdout(io.StringIO()):
            self.inspector.print_report()

    def test_get_summary_returns_expected_structure(self):
        self._write_jsonl(
            "unknown_patterns.jsonl",
            [
                {
                    "features": {"signal_frequency": {"latency_spike": 2}},
                    "pattern_errors": [{"pattern_id": "service_health"}],
                    "runtime_type": "docker",
                }
            ],
        )
        self._write_jsonl("matches.jsonl", [{"pattern_id": "service_health", "runtime_type": "docker"}])
        self._write_jsonl("near_matches.jsonl", [{"pattern_id": "unknown", "runtime_type": "kubernetes"}])

        summary = self.inspector.get_summary()

        self.assertEqual(set(summary), {"volumes", "top_signals", "pattern_crashes", "runtime_distribution"})
        self.assertEqual(summary["volumes"], {"unknowns": 1, "matches": 1, "near_matches": 1})
        self.assertEqual(summary["top_signals"], [("latency_spike", 2)])
        self.assertEqual(summary["pattern_crashes"]["service_health"], 1)
        self.assertEqual(summary["runtime_distribution"]["docker"], 2)
        self.assertEqual(summary["runtime_distribution"]["kubernetes"], 1)

    def _write_jsonl(self, filename: str, records: list[dict]) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with (self.memory_dir / filename).open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    unittest.main()
