from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from core.causal_memory import CausalMemory


class CausalMemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(".milodo") / f"causal_memory_test_{uuid4().hex}"
        self.memory = CausalMemory(self.root)
        self.capture = {
            "features": {
                "signals": ["latency_spike", "dns_flap"],
                "signal_frequency": {"latency_spike": 3, "dns_flap": 1},
            },
            "source": "event_pipeline",
        }

    def tearDown(self) -> None:
        for path in (
            self.root / "unknown_patterns.jsonl",
            self.root / "near_matches.jsonl",
            self.root / "matches.jsonl",
        ):
            if path.exists():
                path.unlink()
        if self.root.exists():
            self.root.rmdir()

    def test_remember_unknown_persists_to_unknown_patterns_jsonl(self):
        self.memory.remember_unknown(self.capture, "docker")

        records = self._read_jsonl(self.root / "unknown_patterns.jsonl")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["pattern_id"], "unknown")
        self.assertFalse(records[0]["near_match"])
        self.assertEqual(records[0]["runtime_type"], "docker")
        self.assertEqual(records[0]["source"], "event_pipeline")
        self.assertEqual(records[0]["features"], self.capture["features"])

    def test_remember_unknown_near_match_writes_to_both_files(self):
        self.memory.remember_unknown(self.capture, "docker", near_match=True)

        unknowns = self._read_jsonl(self.root / "unknown_patterns.jsonl")
        near_matches = self._read_jsonl(self.root / "near_matches.jsonl")

        self.assertEqual(len(unknowns), 1)
        self.assertEqual(len(near_matches), 1)
        self.assertTrue(unknowns[0]["near_match"])
        self.assertEqual(near_matches[0], unknowns[0])

    def test_get_unknowns_returns_all_records(self):
        self.memory.remember_unknown(self.capture, "docker")
        self.memory.remember_unknown(self.capture, "kubernetes", near_match=True)

        records = self.memory.get_unknowns()

        self.assertEqual(len(records), 2)
        self.assertEqual([record["runtime_type"] for record in records], ["docker", "kubernetes"])

    def test_get_near_matches_returns_only_near_match_records(self):
        self.memory.remember_unknown(self.capture, "docker")
        self.memory.remember_unknown(self.capture, "kubernetes", near_match=True)

        records = self.memory.get_near_matches()

        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["near_match"])
        self.assertEqual(records[0]["runtime_type"], "kubernetes")

    def test_records_have_required_fields(self):
        self.memory.remember_unknown(self.capture, "docker")

        record = self.memory.get_unknowns()[0]

        for field in ("timestamp", "pattern_id", "features", "runtime_type", "near_match"):
            self.assertIn(field, record)

    def test_timestamp_is_valid_iso_8601_utc(self):
        self.memory.remember_unknown(self.capture, "docker")

        timestamp = self.memory.get_unknowns()[0]["timestamp"]
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    def test_append_behavior_accumulates_without_overwrite(self):
        self.memory.remember_unknown(self.capture, "docker")
        self.memory.remember_unknown(self.capture, "docker")
        self.memory.remember_unknown(self.capture, "docker")

        self.assertEqual(len(self.memory.get_unknowns()), 3)

    def test_empty_state_returns_empty_lists_safely(self):
        self.assertEqual(self.memory.get_unknowns(), [])
        self.assertEqual(self.memory.get_near_matches(), [])

    def _read_jsonl(self, path: Path) -> list[dict]:
        with path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


if __name__ == "__main__":
    unittest.main()
