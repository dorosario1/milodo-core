import json
from collections import Counter, defaultdict
from pathlib import Path


RESULTS_PATH = Path(".milodo/benchmark_results.json")
SUMMARY_PATH = Path(".milodo/benchmark_summary.json")
CALIBRATION_PATH = Path(".milodo/heuristics_calibration.json")
OUTPUT_PATH = Path(".milodo/heuristics_weights.json")

SEVERITY_ORDER = ["low", "medium", "high", "critical"]


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def increase_severity(severity):
    try:
        index = SEVERITY_ORDER.index(severity)
    except ValueError:
        return "high"

    return SEVERITY_ORDER[min(index + 1, len(SEVERITY_ORDER) - 1)]


def decrease_severity(severity):
    try:
        index = SEVERITY_ORDER.index(severity)
    except ValueError:
        return "low"

    return SEVERITY_ORDER[max(index - 1, 0)]


def build_stats(results):
    counts = Counter()
    severity_counts = defaultdict(Counter)
    weak_counts = Counter()
    premium_counts = Counter()

    for result in results:
        theme_type = result.get("theme_type", "")
        seen_types = set()

        for issue in result.get("issues", []):
            issue_type = issue.get("type")
            if not issue_type:
                continue

            counts[issue_type] += 1
            severity_counts[issue_type][issue.get("severity", "medium")] += 1
            seen_types.add(issue_type)

        for issue_type in seen_types:
            if theme_type == "weak_sites":
                weak_counts[issue_type] += 1
            if theme_type == "premium":
                premium_counts[issue_type] += 1

    total_sites = len(results)
    stats = {}

    all_heuristics = set(counts) | set(weak_counts) | set(premium_counts)
    for heuristic in all_heuristics:
        total_count = counts.get(heuristic, 0)
        most_common_severity = severity_counts[heuristic].most_common(1)
        existing_severity = (
            most_common_severity[0][0]
            if most_common_severity
            else "medium"
        )

        stats[heuristic] = {
            "total_count": total_count,
            "weak_count": weak_counts.get(heuristic, 0),
            "premium_count": premium_counts.get(heuristic, 0),
            "site_ratio": round(total_count / total_sites, 4)
            if total_sites else 0,
            "existing_severity": existing_severity,
        }

    return stats


def build_weights(results, summary, calibration):
    stats = build_stats(results)
    total_sites = summary.get("global_kpi", {}).get("total_sites", len(results))

    too_aggressive = {
        item["heuristic"]
        for item in calibration.get("too_aggressive", [])
    }
    unused_heuristics = set(calibration.get("unused_heuristics", []))
    stable_heuristics = set(
        calibration.get("heuristic_confidence", {}).get("stable", [])
    )

    all_heuristics = (
        set(stats)
        | too_aggressive
        | unused_heuristics
        | stable_heuristics
    )

    weights = {}

    for heuristic in sorted(all_heuristics):
        stat = stats.get(heuristic, {
            "total_count": 0,
            "weak_count": 0,
            "premium_count": 0,
            "site_ratio": 0,
            "existing_severity": "medium",
        })

        severity = stat["existing_severity"] or "medium"
        confidence = 0.5
        status = "active"
        adjustment_reason = "default"

        if heuristic in too_aggressive:
            severity = decrease_severity(severity)
            confidence = round(confidence * 0.7, 2)
            status = "needs_review"
            adjustment_reason = "too_aggressive"
        elif heuristic in unused_heuristics:
            severity = severity or "medium"
            confidence = 0.2
            status = "experimental"
            adjustment_reason = "unused_heuristic"
        elif (
            stat["weak_count"] / max(1, stat["premium_count"])
        ) > 3:
            severity = increase_severity(severity)
            confidence = round(confidence * 1.2, 2)
            status = "active"
            adjustment_reason = "correlated_with_weak_sites"
        elif (
            heuristic in stable_heuristics
            and total_sites
            and 0.20 <= stat["site_ratio"] <= 0.80
        ):
            confidence = 0.7
            status = "active"
            adjustment_reason = "stable_frequency"

        weights[heuristic] = {
            "severity": severity,
            "confidence": confidence,
            "status": status,
            "adjustment_reason": adjustment_reason,
        }

    return weights


def save_weights(weights):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2, ensure_ascii=False)


def print_weights(weights):
    adjusted = [
        (heuristic, data)
        for heuristic, data in weights.items()
        if data["adjustment_reason"] != "default"
    ]
    experimental = [
        heuristic
        for heuristic, data in weights.items()
        if data["status"] == "experimental"
    ]
    stable = [
        heuristic
        for heuristic, data in weights.items()
        if data["adjustment_reason"] == "stable_frequency"
    ]

    print("=== AUTO REWEIGHTING ===")
    print()
    print("Adjusted:")
    for heuristic, data in adjusted:
        print(f"* {heuristic} -> {data['severity']}")
    print()
    print("Experimental:")
    for heuristic in experimental:
        print(f"* {heuristic}")
    print()
    print("Stable:")
    for heuristic in stable:
        print(f"* {heuristic}")


def main():
    results = load_json(RESULTS_PATH)
    summary = load_json(SUMMARY_PATH)
    calibration = load_json(CALIBRATION_PATH)
    weights = build_weights(results, summary, calibration)
    save_weights(weights)
    print_weights(weights)


if __name__ == "__main__":
    main()
