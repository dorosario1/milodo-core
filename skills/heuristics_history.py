import argparse
import json
from datetime import datetime
from pathlib import Path


WEIGHTS_PATH = Path(".milodo/heuristics_weights.json")
SUMMARY_PATH = Path(".milodo/benchmark_summary.json")
CALIBRATION_PATH = Path(".milodo/heuristics_calibration.json")
HISTORY_PATH = Path(".milodo/heuristics_history.json")


def _empty_history():
    return {
        "snapshots": [],
        "evolution": {
            "severity_changes": [],
            "confidence_changes": [],
            "new_stable": [],
            "new_experimental": [],
        },
    }


def _load_json(path, default=None):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    history = _load_json(HISTORY_PATH, _empty_history())
    if not isinstance(history, dict):
        return _empty_history()

    history.setdefault("snapshots", [])
    history.setdefault("evolution", {})
    history["evolution"].setdefault("severity_changes", [])
    history["evolution"].setdefault("confidence_changes", [])
    history["evolution"].setdefault("new_stable", [])
    history["evolution"].setdefault("new_experimental", [])
    return history


def create_snapshot():
    weights = _load_json(WEIGHTS_PATH, {})
    summary = _load_json(SUMMARY_PATH, {})
    calibration = _load_json(CALIBRATION_PATH, {})

    return {
        "timestamp": datetime.now().isoformat(),
        "weights": weights or {},
        "summary": summary or {},
        "calibration": calibration or {},
    }


def compare_snapshots(previous, current):
    evolution = {
        "severity_changes": [],
        "confidence_changes": [],
        "new_stable": [],
        "new_experimental": [],
    }

    previous_weights = previous.get("weights", {}) if previous else {}
    current_weights = current.get("weights", {})

    all_heuristics = set(previous_weights) | set(current_weights)

    for heuristic in sorted(all_heuristics):
        old_data = previous_weights.get(heuristic, {})
        new_data = current_weights.get(heuristic, {})

        old_severity = old_data.get("severity")
        new_severity = new_data.get("severity")
        if old_severity and new_severity and old_severity != new_severity:
            evolution["severity_changes"].append({
                "heuristic": heuristic,
                "old": old_severity,
                "new": new_severity,
            })

        old_confidence = old_data.get("confidence")
        new_confidence = new_data.get("confidence")
        if (
            old_confidence is not None
            and new_confidence is not None
            and abs(new_confidence - old_confidence) > 0.15
        ):
            evolution["confidence_changes"].append({
                "heuristic": heuristic,
                "old": old_confidence,
                "new": new_confidence,
                "delta": round(new_confidence - old_confidence, 3),
            })

        if (
            old_confidence is not None
            and new_confidence is not None
            and old_confidence > 0.7
            and new_confidence > 0.7
        ):
            evolution["new_stable"].append({
                "heuristic": heuristic,
                "confidence": new_confidence,
            })

        if (
            old_confidence is not None
            and new_confidence is not None
            and old_confidence < 0.3
            and new_confidence < 0.3
        ):
            evolution["new_experimental"].append({
                "heuristic": heuristic,
                "confidence": new_confidence,
            })

    return evolution


def save_history(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def append_snapshot():
    history = load_history()
    snapshot = create_snapshot()
    previous = history["snapshots"][-1] if history["snapshots"] else None
    evolution = compare_snapshots(previous, snapshot)

    history["snapshots"].append(snapshot)
    history["evolution"] = evolution
    save_history(history)

    return snapshot, evolution


def print_run(snapshot, evolution):
    print("=== HEURISTICS HISTORY ===")
    print()
    print("Snapshot saved:")
    print(snapshot["timestamp"])
    print()

    print("Severity changes:")
    for item in evolution["severity_changes"]:
        print(f"* {item['heuristic']}: {item['old']} -> {item['new']}")
    print()

    print("Confidence changes:")
    for item in evolution["confidence_changes"]:
        print(
            f"* {item['heuristic']}: "
            f"{item['old']} -> {item['new']} "
            f"(delta {item['delta']})"
        )
    print()

    print("New stable:")
    for item in evolution["new_stable"]:
        print(f"* {item['heuristic']}")
    print()

    print("New experimental:")
    for item in evolution["new_experimental"]:
        print(f"* {item['heuristic']}")


def print_report():
    history = load_history()
    print(json.dumps(history, indent=2, ensure_ascii=False))


def print_last():
    history = load_history()
    if not history["snapshots"]:
        print("{}")
        return

    print(json.dumps(history["snapshots"][-1], indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true", help="Afficher historique complet")
    parser.add_argument("--last", action="store_true", help="Afficher le dernier snapshot")
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    if args.last:
        print_last()
        return

    snapshot, evolution = append_snapshot()
    print_run(snapshot, evolution)


if __name__ == "__main__":
    main()
