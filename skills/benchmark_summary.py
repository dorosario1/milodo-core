import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


RESULTS_PATH = Path(".milodo/benchmark_results.json")
SUMMARY_PATH = Path(".milodo/benchmark_summary.json")

WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 1,
}


def load_results():
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(f"Résultats benchmark introuvables: {RESULTS_PATH}")

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("benchmark_results.json doit contenir une liste")

    return data


def _site_label(url):
    parsed = urlparse(url or "")
    return parsed.netloc or url or "unknown"


def _quality_score(issues):
    total_weight = sum(
        WEIGHTS.get(issue.get("severity", "low"), 1)
        for issue in issues
    )
    return max(0, 100 - total_weight)


def build_summary(results):
    total_sites = len(results)
    successful_fetches = len([r for r in results if not r.get("error")])
    execution_times = [r.get("execution_time", 0) for r in results]
    total_issues = sum(len(r.get("issues", [])) for r in results)

    heuristic_counts = Counter()
    failure_counts = Counter()
    severity_counts = Counter()
    heuristics_by_category = defaultdict(Counter)
    scored_sites = []

    for result in results:
        issues = result.get("issues", [])
        theme_type = result.get("theme_type", "unknown")

        for issue in issues:
            issue_type = issue.get("type", "unknown")
            severity = issue.get("severity", "unknown")
            heuristic_counts[issue_type] += 1
            severity_counts[severity] += 1
            heuristics_by_category[theme_type][issue_type] += 1

        if result.get("error"):
            failure_counts[result.get("error_type", "fetch_error")] += 1

        scored_sites.append({
            "url": result.get("url", ""),
            "site": _site_label(result.get("url", "")),
            "score": _quality_score(issues),
            "issues": len(issues),
            "execution_time": round(result.get("execution_time", 0), 3),
        })

    top_heuristics = [
        {"type": issue_type, "count": count}
        for issue_type, count in heuristic_counts.most_common()
    ]

    top_slowest_sites = sorted(
        [
            {
                "url": result.get("url", ""),
                "site": _site_label(result.get("url", "")),
                "execution_time": round(result.get("execution_time", 0), 3),
            }
            for result in results
        ],
        key=lambda item: item["execution_time"],
        reverse=True,
    )[:10]

    best_sites = sorted(
        scored_sites,
        key=lambda item: (-item["score"], item["issues"], item["site"]),
    )[:10]

    worst_sites = sorted(
        scored_sites,
        key=lambda item: (item["score"], -item["issues"], item["site"]),
    )[:10]

    global_kpi = {
        "total_sites": total_sites,
        "fetch_success_rate": round(
            (successful_fetches / total_sites) * 100,
            1,
        ) if total_sites else 0,
        "avg_response_time": round(
            sum(execution_times) / total_sites,
            3,
        ) if total_sites else 0,
        "avg_issues_per_site": round(
            total_issues / total_sites,
            2,
        ) if total_sites else 0,
        "sites_0_issue": len([r for r in results if not r.get("issues", [])]),
        "top_failure_types": [
            {"type": failure_type, "count": count}
            for failure_type, count in failure_counts.most_common()
        ],
        "heuristics_par_categorie": {
            category: dict(counter.most_common())
            for category, counter in heuristics_by_category.items()
        },
        "severity_distribution": dict(severity_counts),
    }

    return {
        "global_kpi": global_kpi,
        "top_heuristics": top_heuristics,
        "top_slowest_sites": top_slowest_sites,
        "best_sites": best_sites,
        "worst_sites": worst_sites,
    }


def save_summary(summary):
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def print_summary(summary):
    global_kpi = summary["global_kpi"]

    print("=== GLOBAL KPI ===")
    print(f"Sites: {global_kpi['total_sites']}")
    print(f"Fetch success: {global_kpi['fetch_success_rate']}%")
    print(f"Avg response time: {global_kpi['avg_response_time']}s")
    print(f"Avg issues/site: {global_kpi['avg_issues_per_site']}")
    print()

    print("=== TOP HEURISTICS ===")
    for item in summary["top_heuristics"][:10]:
        print(f"{item['type']}: {item['count']}")
    print()

    print("=== TOP SLOWEST SITES ===")
    for item in summary["top_slowest_sites"]:
        print(f"{item['site']} {item['execution_time']}s")
    print()

    print("=== WORST SITES ===")
    for item in summary["worst_sites"]:
        print(f"{item['site']} score={item['score']}")
    print()

    print("=== BEST SITES ===")
    for item in summary["best_sites"]:
        print(f"{item['site']} score={item['score']}")


def main():
    results = load_results()
    summary = build_summary(results)
    save_summary(summary)
    print_summary(summary)


if __name__ == "__main__":
    main()
