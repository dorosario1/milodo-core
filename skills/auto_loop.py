import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = BASE_DIR / ".milodo" / "auto_loop.log"
BENCHMARK_RESULTS_PATH = BASE_DIR / ".milodo" / "benchmark_results.json"


def log(message):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def run_step(name, command):
    log(f"START {name}")
    try:
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            check=False,
        )
        if result.returncode == 0:
            log(f"OK {name}")
            return True

        log(f"FAIL {name}: returncode={result.returncode}")
        return False
    except Exception as error:
        log(f"FAIL {name}: {type(error).__name__}")
        return False


def benchmark_is_stale():
    if not BENCHMARK_RESULTS_PATH.exists():
        return True

    modified_at = datetime.fromtimestamp(
        BENCHMARK_RESULTS_PATH.stat().st_mtime
    )
    return datetime.now() - modified_at > timedelta(hours=24)


def run_full_pipeline():
    steps = [
        (
            "benchmark",
            [sys.executable, "skills/heuristics_benchmark.py", "--run"],
        ),
        ("summary", [sys.executable, "skills/benchmark_summary.py"]),
        ("calibration", [sys.executable, "skills/heuristics_calibration.py"]),
        ("reweighting", [sys.executable, "skills/auto_reweighting.py"]),
        ("history", [sys.executable, "skills/heuristics_history.py"]),
    ]

    success = True
    for name, command in steps:
        success = run_step(name, command) and success
    return success


def run_update_pipeline():
    steps = [
        ("summary", [sys.executable, "skills/benchmark_summary.py"]),
        ("calibration", [sys.executable, "skills/heuristics_calibration.py"]),
        ("reweighting", [sys.executable, "skills/auto_reweighting.py"]),
        ("history", [sys.executable, "skills/heuristics_history.py"]),
    ]

    success = True
    for name, command in steps:
        success = run_step(name, command) and success
    return success


def run_schedule(interval):
    log(f"START schedule interval={interval}")
    try:
        while True:
            if benchmark_is_stale():
                run_full_pipeline()
            else:
                run_update_pipeline()
            time.sleep(interval)
    except KeyboardInterrupt:
        log("STOP schedule: KeyboardInterrupt")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Lancer la pipeline complète")
    parser.add_argument("--update", action="store_true", help="Lancer la pipeline sans benchmark")
    parser.add_argument("--schedule", action="store_true", help="Lancer en boucle")
    parser.add_argument("--interval", type=int, default=3600, help="Intervalle du scheduler en secondes")
    args = parser.parse_args()

    if args.full:
        run_full_pipeline()
    elif args.update:
        run_update_pipeline()
    elif args.schedule:
        run_schedule(args.interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
