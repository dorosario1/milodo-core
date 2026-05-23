from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.soak_long_term import generate_long_term_report, save_runtime_snapshot
from core.soak_persistence import graceful_shutdown, resume_previous_soak, rotate_old_reports, save_soak_report
from core.soak_runner import SoakRunner


DEFAULT_PATTERNS = ["resource_exhaustion", "service_health", "routing_priority"]
DEFAULT_RUNTIMES = ["docker"]
REPORTS_DIR = ROOT / "reports" / "soak"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MILODO long soak test")
    parser.add_argument("--interval", type=float, default=300.0)
    parser.add_argument("--cycles", type=int, default=288)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--rotate-keep", type=int, default=48)
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "snapshots").mkdir(parents=True, exist_ok=True)

    resume_state = resume_previous_soak(REPORTS_DIR) if args.resume else {
        "schema_version": "1.0",
        "resumable": False,
        "next_cycle": 1,
    }
    runner = SoakRunner(patterns=DEFAULT_PATTERNS, runtimes=DEFAULT_RUNTIMES)
    start_report = {
        "schema_version": "1.0",
        "event": "long_soak_start",
        "interval": args.interval,
        "max_cycles": args.cycles,
        "estimated_hours": round((args.interval * args.cycles) / 3600, 2),
        "patterns": DEFAULT_PATTERNS,
        "runtimes": DEFAULT_RUNTIMES,
        "resume": resume_state,
    }
    save_soak_report(start_report, REPORTS_DIR)
    save_runtime_snapshot(REPORTS_DIR, patterns=DEFAULT_PATTERNS)

    try:
        report = runner.run_soak_test(interval=args.interval, max_cycles=args.cycles)
        save_soak_report(report, REPORTS_DIR)
        save_runtime_snapshot(REPORTS_DIR, patterns=DEFAULT_PATTERNS)
        long_term = generate_long_term_report(REPORTS_DIR)
        rotated = rotate_old_reports(REPORTS_DIR, keep=args.rotate_keep)
        summary = {
            "schema_version": "1.0",
            "stable": report["stable"],
            "memory_growth_detected": report["memory_growth_detected"],
            "strategy_regression": report["strategy_regression"],
            "corruption_detected": report["corruption_detected"],
            "benchmark_consistent": report["benchmark_consistent"],
            "cycles": report["cycles"],
            "transfer_consistency": report["transfer_consistency"],
            "long_term_stable": long_term["stable"],
            "rotated_reports": len(rotated),
            "reports_dir": str(REPORTS_DIR),
        }
        print(json.dumps(summary, indent=2))
        return 0 if summary["stable"] and not summary["corruption_detected"] else 2
    except KeyboardInterrupt:
        shutdown = graceful_shutdown(
            runner,
            {
                "schema_version": "1.0",
                "event": "long_soak_interrupted",
                "stable": False,
                "cycles": 0,
            },
            REPORTS_DIR,
        )
        save_runtime_snapshot(REPORTS_DIR, patterns=DEFAULT_PATTERNS)
        generate_long_term_report(REPORTS_DIR)
        print(json.dumps(shutdown, indent=2))
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

