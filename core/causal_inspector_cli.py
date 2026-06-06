from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .causal_inspector import CausalInspector


RUNTIMES = {"docker", "kubernetes", "baremetal", "unknown"}


def main() -> int:
    args = _parse_args()
    inspector = CausalInspector(args.memory_dir)

    unknowns = inspector.load_unknowns()
    matches = inspector.load_matches()
    near_matches = inspector.load_near_matches()

    unknowns = _apply_filters(unknowns, args.runtime, args.since)
    matches = _apply_filters(matches, args.runtime, args.since)
    near_matches = _apply_filters(near_matches, args.runtime, args.since)

    summary = inspector.get_summary(
        unknowns=unknowns,
        matches=matches,
        near_matches=near_matches,
        top_limit=args.top,
    )

    if args.format == "json":
        print(json.dumps(_json_summary(summary), indent=2))
        return 0

    _print_human(summary, args.runtime, args.since)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect MILODO causal memory")
    parser.add_argument("--memory-dir", type=Path, default=Path(".milodo/causal_memory"))
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--runtime", choices=(*sorted(RUNTIMES), "all"), default="all")
    parser.add_argument("--since", type=int, default=None)
    return parser.parse_args()


def _apply_filters(
    records: list[dict[str, Any]],
    runtime: str,
    since_days: int | None,
) -> list[dict[str, Any]]:
    filtered = records
    if runtime != "all":
        filtered = [record for record in filtered if record.get("runtime_type", "unknown") == runtime]
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        filtered = [record for record in filtered if _is_since(record, cutoff)]
    return filtered


def _is_since(record: dict[str, Any], cutoff: datetime) -> bool:
    timestamp = record.get("timestamp")
    if not timestamp:
        return True
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed >= cutoff


def _json_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "volumes": summary["volumes"],
        "top_signals": summary["top_signals"],
        "pattern_crashes": dict(summary["pattern_crashes"]),
        "runtime_distribution": dict(summary["runtime_distribution"]),
    }


def _print_human(summary: dict[str, Any], runtime: str, since_days: int | None) -> None:
    print("MILODO Causal Memory Inspector")
    print("==============================")
    filters = []
    if runtime != "all":
        filters.append(f"runtime={runtime}")
    if since_days is not None:
        filters.append(f"since={since_days}d")
    if filters:
        print(f"Filters: {', '.join(filters)}")
        print("")

    volumes = summary["volumes"]
    print("Volumes")
    print("-------")
    print(f"Unknowns: {volumes['unknowns']}")
    print(f"Matches: {volumes['matches']}")
    print(f"Near matches: {volumes['near_matches']}")
    print("")

    print("Top unknown signals")
    print("-------------------")
    if summary["top_signals"]:
        for signal, count in summary["top_signals"]:
            print(f"- {signal}: {count}")
    else:
        print("- none")
    print("")

    print("Pattern crashes")
    print("---------------")
    crashes = summary["pattern_crashes"]
    if crashes:
        for pattern, count in crashes.most_common():
            print(f"- {pattern}: {count}")
    else:
        print("- none")
    print("")

    print("Runtime distribution")
    print("--------------------")
    runtime_distribution = summary["runtime_distribution"]
    total = sum(runtime_distribution.values())
    if runtime_distribution:
        for runtime_name, count in runtime_distribution.most_common():
            percentage = (count / total * 100) if total else 0.0
            print(f"- {runtime_name}: {count} ({percentage:.1f}%)")
    else:
        print("- none")
    recent_events = [record for record in CausalInspector().load_unknowns() if record.get("source") == "causal_engine_event"][-5:]
    if recent_events:
        print("")
        print("Recent Causal Events")
        print("--------------------")
        for event in recent_events:
            signals = event.get("features", {}).get("signals", [])
            print(f"- {(signals[0] if signals else 'unknown')}: {event.get('runtime_type', 'unknown')} @ {event.get('timestamp', 'unknown')}")


if __name__ == "__main__":
    raise SystemExit(main())
