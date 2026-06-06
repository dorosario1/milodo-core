import json
from collections import Counter
from pathlib import Path


RESULTS_PATH = Path(".milodo/benchmark_results.json")
SUMMARY_PATH = Path(".milodo/benchmark_summary.json")
OUTPUT_PATH = Path(".milodo/heuristics_calibration.json")

KNOWN_HEURISTICS = [
    "no_h1",
    "seo_missing",
    "seo_weak",
    "missing_contact",
    "missing_whatsapp",
    "missing_contact_form",
    "no_nav",
    "navigation_missing",
    "navigation_ux",
    "form_too_long",
    "form_no_placeholder",
    "form_friction",
    "whatsapp_below_fold",
    "whatsapp_weak_message",
    "whatsapp_ux",
    "performance_lazy_missing",
    "performance_cls_risk",
    "performance_too_many_images",
    "performance_excessive_scripts",
    "performance_multiple_fonts",
    "performance_missing_preconnect",
    "mobile_video_autoplay",
    "cta_weak",
    "trust_missing",
    "conversion_weak",
    "hero_weak",
    "accessibility",
]

REVIEW_ISSUES = {"no_h1", "no_nav", "seo_missing"}


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze(results, summary):
    total_sites = summary.get("global_kpi", {}).get("total_sites", len(results))
    issue_counts = Counter()
    premium_sites = []

    for result in results:
        issues = result.get("issues", [])
        issue_counts.update(issue.get("type", "unknown") for issue in issues)

        if result.get("theme_type") == "premium":
            total_weight = sum(
                {
                    "critical": 10,
                    "high": 5,
                    "medium": 2,
                    "low": 1,
                }.get(issue.get("severity", "low"), 1)
                for issue in issues
            )
            score = max(0, 100 - total_weight)
            premium_sites.append({
                "url": result.get("url", ""),
                "score": score,
                "issues": issues,
            })

    unused_heuristics = [
        heuristic
        for heuristic in KNOWN_HEURISTICS
        if issue_counts.get(heuristic, 0) == 0
    ]

    too_aggressive = [
        {
            "heuristic": heuristic,
            "count": count,
            "site_ratio": round(count / total_sites, 2) if total_sites else 0,
            "flag": "too_aggressive",
        }
        for heuristic, count in issue_counts.items()
        if total_sites and count / total_sites > 0.40
    ]

    under_triggering = [
        {
            "heuristic": heuristic,
            "count": issue_counts.get(heuristic, 0),
            "flag": "under_triggering",
        }
        for heuristic in KNOWN_HEURISTICS
        if issue_counts.get(heuristic, 0) <= 1
    ]

    potential_false_positives = []
    for site in premium_sites:
        issue_types = {issue.get("type") for issue in site["issues"]}
        suspicious_types = sorted(issue_types & REVIEW_ISSUES)

        if site["score"] < 90 or suspicious_types:
            potential_false_positives.append({
                "url": site["url"],
                "score": site["score"],
                "heuristics": suspicious_types,
            })

    calibration_suggestions = [
        {
            "heuristic": "no_h1",
            "issue": "false_positive_on_js_sites",
            "recommendation": "Ignorer si React hydration détectée.",
        },
        {
            "heuristic": "missing_whatsapp",
            "issue": "too_africa_specific",
            "recommendation": "Appliquer seulement sur catégories tourism/mobile_first/weak_sites.",
        },
    ]

    if issue_counts.get("missing_contact", 0):
        calibration_suggestions.append({
            "heuristic": "missing_contact",
            "issue": "legacy_bucket_too_broad",
            "recommendation": "Remplacer progressivement par missing_whatsapp et missing_contact_form.",
        })

    stable = []
    needs_review = []
    experimental = []

    too_aggressive_names = {item["heuristic"] for item in too_aggressive}
    suspicious_names = {
        heuristic
        for item in potential_false_positives
        for heuristic in item["heuristics"]
    }

    for heuristic in KNOWN_HEURISTICS:
        count = issue_counts.get(heuristic, 0)

        if count == 1:
            experimental.append(heuristic)
        elif (
            count == 0
            or heuristic in too_aggressive_names
            or heuristic in suspicious_names
        ):
            needs_review.append(heuristic)
        elif count > 1:
            stable.append(heuristic)

    return {
        "unused_heuristics": unused_heuristics,
        "too_aggressive": too_aggressive,
        "under_triggering": under_triggering,
        "potential_false_positives": potential_false_positives,
        "calibration_suggestions": calibration_suggestions,
        "heuristic_confidence": {
            "stable": stable,
            "needs_review": needs_review,
            "experimental": experimental,
        },
    }


def save_analysis(analysis):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def print_analysis(analysis):
    print("=== HEURISTICS ANALYSIS ===")
    print()
    print("Unused heuristics:")
    for heuristic in analysis["unused_heuristics"]:
        print(f"* {heuristic}")
    print()

    print("Too aggressive:")
    for item in analysis["too_aggressive"]:
        print(f"* {item['heuristic']} ({item['count']})")
    print()

    print("Potential false positives:")
    for item in analysis["potential_false_positives"]:
        heuristics = ", ".join(item["heuristics"]) or "premium_score_below_90"
        print(f"* {item['url']} -> {heuristics}")
    print()

    print("Calibration suggestions:")
    for item in analysis["calibration_suggestions"]:
        print(
            f"* {item['heuristic']}: "
            f"{item['issue']} -> {item['recommendation']}"
        )


def main():
    results = load_json(RESULTS_PATH)
    summary = load_json(SUMMARY_PATH)
    analysis = analyze(results, summary)
    save_analysis(analysis)
    print_analysis(analysis)


if __name__ == "__main__":
    main()
