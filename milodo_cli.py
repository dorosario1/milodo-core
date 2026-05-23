from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.causal_engine import CausalEngine
from core.event_pipeline import EventPipeline
from core.runtime_context import RuntimeContext, healthcheck
from core.strategy_engine import StrategyEngine
from core.validation_engine import ValidationEngine
from memory.causal_memory import CausalMemory


def run_pattern(pattern: str, runtime: str) -> dict:
    context = RuntimeContext(runtime=runtime, root=Path(__file__).resolve().parent)
    events = EventPipeline(context).collect(pattern)
    causal = CausalEngine(context).identify(events)
    strategy = StrategyEngine(context).apply(causal)
    validation = ValidationEngine(context).validate(strategy)
    result = {
        "schema_version": "1.0",
        "runtime": runtime,
        "incident": "detected" if events else "none",
        "causal_engine": causal,
        "strategy_engine": strategy,
        "validation_engine": validation,
    }
    CausalMemory().persist_execution(result)
    return result


def run_resource_exhaustion(runtime: str) -> dict:
    return run_pattern("resource_exhaustion", runtime)


def main() -> int:
    parser = argparse.ArgumentParser(prog="milodo_cli.py")
    parser.add_argument(
        "pattern",
        nargs="?",
        choices=["resource_exhaustion", "service_health", "routing_priority"],
    )
    parser.add_argument("--runtime", default="docker", choices=["docker", "kubernetes", "local"])
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()

    if args.healthcheck:
        print(json.dumps(healthcheck(Path(__file__).resolve().parent), indent=2))
        return 0

    if args.pattern:
        result = run_pattern(args.pattern, args.runtime)
        print("incident detected")
        print(f"causal_engine identified {result['causal_engine']['cause']}")
        print(f"strategy_engine applied {result['strategy_engine']['strategy']}")
        print(f"validation_engine {result['validation_engine']['message']}")
        if result["validation_engine"]["rollback_available"]:
            print("rollback available")
        print(json.dumps(result, indent=2))
        return 0 if result["validation_engine"]["stable"] else 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
