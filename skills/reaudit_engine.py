import json
import logging
from datetime import datetime
from pathlib import Path


SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 1,
}

LOG_PATH = ".milodo/reaudit_engine.log"


def setup_logger():
    log_path = Path(LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("milodo_reaudit_engine")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


LOGGER = setup_logger()


def normalize_issue(issue):
    return {
        "type": issue.get("type", ""),
        "severity": issue.get("severity", "low"),
        "confidence": float(issue.get("confidence", 0.5)),
    }


def issue_key(issue):
    normalized = normalize_issue(issue)
    return (
        normalized["type"],
        normalized["severity"],
    )


def compare_issues(before, after):
    before_normalized = [normalize_issue(issue) for issue in before]
    after_normalized = [normalize_issue(issue) for issue in after]

    before_keys = {issue_key(issue) for issue in before_normalized}
    after_keys = {issue_key(issue) for issue in after_normalized}

    fixed_keys = before_keys - after_keys
    remaining_keys = before_keys & after_keys
    new_keys = after_keys - before_keys

    return {
        "fixed_issues": [
            issue for issue in before_normalized
            if issue_key(issue) in fixed_keys
        ],
        "remaining_issues": [
            issue for issue in before_normalized
            if issue_key(issue) in remaining_keys
        ],
        "new_issues": [
            issue for issue in after_normalized
            if issue_key(issue) in new_keys
        ],
    }


def compute_quality_score(issues):
    penalty = sum(
        SEVERITY_WEIGHTS.get(
            normalize_issue(issue)["severity"],
            1,
        )
        for issue in issues
    )
    return round(max(0, 100 - penalty), 2)


def compute_improvement(before_score, after_score):
    if before_score == 0:
        return 0.0

    return round(
        ((after_score - before_score) / before_score) * 100,
        2,
    )


def compute_success_rate(before, fixed):
    if len(before) == 0:
        return 100.0

    return round((len(fixed) / len(before)) * 100, 2)


def generate_summary(result):
    improvement = result.get("improvement", 0)

    if improvement > 0:
        status = "improved"
    elif improvement < 0:
        status = "degraded"
    else:
        status = "stable"

    return {
        "fixed_count": len(result.get("fixed_issues", [])),
        "remaining_count": len(result.get("remaining_issues", [])),
        "new_count": len(result.get("new_issues", [])),
        "quality_delta": round(
            result.get("quality_score_after", 0)
            - result.get("quality_score_before", 0),
            2,
        ),
        "status": status,
    }


def generate_report(before_issues, after_issues):
    comparison = compare_issues(before_issues, after_issues)
    before_score = compute_quality_score(before_issues)
    after_score = compute_quality_score(after_issues)
    improvement = compute_improvement(before_score, after_score)
    success_rate = compute_success_rate(
        before_issues,
        comparison["fixed_issues"],
    )

    result = {
        "success": True,
        "fixed_issues": comparison["fixed_issues"],
        "remaining_issues": comparison["remaining_issues"],
        "new_issues": comparison["new_issues"],
        "quality_score_before": before_score,
        "quality_score_after": after_score,
        "improvement": improvement,
        "success_rate": success_rate,
        "summary": {},
    }
    result["summary"] = generate_summary(result)

    LOGGER.info(
        "reaudit success fixed=%s remaining=%s new=%s status=%s",
        result["summary"]["fixed_count"],
        result["summary"]["remaining_count"],
        result["summary"]["new_count"],
        result["summary"]["status"],
    )
    return result


def save_report(report):
    reports_dir = Path(".milodo/reaudit_reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"reaudit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = reports_dir / filename

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    LOGGER.info("reaudit report saved path=%s", report_path)
    return str(report_path)


def run(action="reaudit", **kwargs):
    if action == "reaudit":
        report = generate_report(
            before_issues=kwargs.get("before_issues", []),
            after_issues=kwargs.get("after_issues", []),
        )
        save_report(report)
        return report

    if action == "compare":
        return compare_issues(
            before=kwargs.get("before_issues", []),
            after=kwargs.get("after_issues", []),
        )

    return {
        "success": False,
        "error": f"Action inconnue: {action}",
    }
