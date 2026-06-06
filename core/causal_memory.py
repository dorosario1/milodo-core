from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CausalMemory:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(".milodo") / "causal_memory"
        self.unknown_path = self.root / "unknown_patterns.jsonl"
        self.near_match_path = self.root / "near_matches.jsonl"
        self.match_path = self.root / "matches.jsonl"

    def remember_unknown(
        self,
        capture: dict[str, Any],
        runtime_type: str,
        near_match: bool = False,
    ) -> None:
        record = self._unknown_record(capture, runtime_type, near_match)
        self._append_jsonl(self.unknown_path, record)
        if near_match:
            self._append_jsonl(self.near_match_path, record)

    def remember_match(self, pattern_id: str, confidence: float, runtime_type: str) -> None:
        _ = confidence
        record = {
            "timestamp": self._utc_timestamp(),
            "pattern_id": pattern_id,
            "near_match": False,
            "features": {
                "signals": [],
                "signal_frequency": {},
            },
            "runtime_type": runtime_type,
            "source": "pattern_registry",
        }
        self._append_jsonl(self.match_path, record)

    def get_unknowns(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.unknown_path)

    def get_near_matches(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.near_match_path)

    def _unknown_record(
        self,
        capture: dict[str, Any],
        runtime_type: str,
        near_match: bool,
    ) -> dict[str, Any]:
        features = capture.get("features", capture)
        return {
            "timestamp": self._utc_timestamp(),
            "pattern_id": "unknown",
            "near_match": near_match,
            "features": {
                "signals": list(features.get("signals", [])),
                "signal_frequency": dict(features.get("signal_frequency", {})),
            },
            "runtime_type": runtime_type,
            "source": capture.get("source", "event_pipeline"),
        }

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _utc_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
