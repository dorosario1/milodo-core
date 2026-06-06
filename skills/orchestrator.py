import json
import logging
from datetime import datetime
from pathlib import Path
from skills.executor import run as executor_run
from skills.reaudit_engine import generate_report as reaudit
from skills.sandbox_workspace import SandboxWorkspace, flatten_backup_name


LOG_PATH = ".milodo/orchestrator.log"
REPORTS_PATH = ".milodo/orchestrations"

SEVERITY_WEIGHTS = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "low": 1,
}


def setup_logger():
    log_path = Path(LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("milodo_orchestrator")
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


def compute_quality_score(issues):
    penalties = sum(
        SEVERITY_WEIGHTS.get(issue.get("severity", "low"), 1)
        for issue in issues
    )
    return float(max(0, 100 - penalties))


def _extract_score(audit):
    if not isinstance(audit, dict):
        return None

    for key in ("score", "global_score", "overall_score"):
        value = audit.get(key)
        if value is not None:
            return float(value)

    return None


def _compare_scores(score_before, score_after):
    if score_before is None or score_after is None:
        return "unknown"

    if score_after > score_before:
        return "improved"

    if score_after == score_before:
        return "stable"

    return "degraded"


def _rollback_workspace(workspace_path, filename):
    if not workspace_path:
        return None

    workspace_root = Path(workspace_path)
    workspace = SandboxWorkspace(workspace_root.name)
    backup_name = flatten_backup_name(filename)
    backup_path = workspace.backups_dir / f"{backup_name}.bak"
    patched_path = workspace.patched_dir / filename

    if not backup_path.exists():
        return None

    patched_path.parent.mkdir(parents=True, exist_ok=True)
    patched_path.write_bytes(backup_path.read_bytes())
    return str(patched_path)


def run_orchestrator(
    original_html,
    patched_html,
    audit_before=None,
    workspace_name=None,
    filename="index.html",
):
    """
    Valide un patch HTML dans un workspace sandbox et décide s'il est acceptable.
    """
    try:
        from skills.audit_engine import audit_html

        audit_before = audit_before or audit_html(original_html)
        score_before = _extract_score(audit_before)
        audit_after = audit_html(patched_html)
        score_after = _extract_score(audit_after)
        score_delta = (
            round(score_after - score_before, 2)
            if score_before is not None and score_after is not None
            else None
        )

        sandbox_result = executor_run(
            action="sandbox_patch",
            original_html=original_html,
            patched_html=patched_html,
            filename=filename,
            dry_run=False,
        )
        workspace_path = sandbox_result.get("workspace_path")

        before_issues = audit_before.get("issues", [])
        after_issues = audit_after.get("issues", [])
        reaudit(before_issues, after_issues)

        score_comparison = _compare_scores(score_before, score_after)
        accepted = (
            sandbox_result.get("success", False)
            and score_comparison in ("improved", "stable")
        )
        rollback_required = not accepted
        rolled_back = False
        rollback_path = None

        if accepted:
            decision_reason = f"Patch {score_comparison} — score {score_before} → {score_after}"
        elif score_comparison == "degraded":
            decision_reason = (
                f"Patch degraded — score {score_before} → "
                f"{score_after} (delta={score_delta})"
            )
        else:
            decision_reason = "Unable to compare scores — rolling back by default"

        if rollback_required:
            rollback_path = _rollback_workspace(workspace_path, filename)
            rolled_back = rollback_path is not None

        return {
            "accepted": accepted,
            "rollback_required": rollback_required,
            "rolled_back": rolled_back,
            "rollback_path": rollback_path,
            "score_before": score_before,
            "score_after": score_after,
            "score_delta": score_delta,
            "workspace_path": workspace_path,
            "patch_report": sandbox_result.get("report", {}),
            "audit_after": audit_after,
            "error": None,
            "score_comparison": score_comparison,
            "decision_reason": decision_reason,
        }
    except Exception as error:
        return {
            "accepted": False,
            "rollback_required": True,
            "rolled_back": False,
            "rollback_path": None,
            "score_before": _extract_score(audit_before),
            "score_after": None,
            "score_delta": None,
            "workspace_path": None,
            "patch_report": {},
            "audit_after": {},
            "error": str(error),
            "score_comparison": "error",
            "decision_reason": "exception",
        }


def run_audit(url, html=None):
    if html is not None:
        from skills.heuristics_engine import analyze

        result = analyze(html, url)
    else:
        from skills.audit_router import run as audit_router_run

        result = audit_router_run(action="audit_url", url=url)

    issues = result.get("issues", []) if isinstance(result, dict) else []
    return {
        "issues": issues,
        "quality_score": compute_quality_score(issues),
    }


def run_architect(issues):
    try:
        from skills.architect_agent import run as architect_run

        return architect_run(
            action="plan",
            issues=issues,
        )
    except Exception as error:
        LOGGER.warning("architect fallback used: %s", error)
        return {
            "success": False,
            "fallback": True,
            "message": "architect_agent unavailable",
            "steps": [
                {
                    "issue_type": issue.get("type", ""),
                    "severity": issue.get("severity", "low"),
                }
                for issue in issues
            ],
        }


def run_coding(issue):
    from skills.coding_agent import run as coding_run

    return coding_run(
        action="fix_issue",
        issue=issue,
        target_file="simulation.html",
        apply=False,
    )


def run_executor(patch, dry_run=True):
    from skills.executor import run as executor_run

    return executor_run(
        action="patch",
        patch=patch,
        dry_run=dry_run,
    )


def run_reaudit(before_issues, after_issues):
    from skills.reaudit_engine import run as reaudit_run

    return reaudit_run(
        action="reaudit",
        before_issues=before_issues,
        after_issues=after_issues,
    )


def simulate_after_issues(before_issues, execution_results):
    """Simule les issues après exécution des patches."""
    remaining = list(before_issues)

    for exec_result in execution_results:
        if exec_result.get("success", False):
            issue_type = exec_result.get("issue_type")

            for i, issue in enumerate(remaining):
                if issue.get("type") == issue_type:
                    remaining.pop(i)
                    break

    return remaining


def save_orchestration_report(report):
    reports_path = Path(REPORTS_PATH)
    reports_path.mkdir(parents=True, exist_ok=True)
    filename = f"orchestration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = reports_path / filename

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    LOGGER.info("orchestration report saved path=%s", report_path)
    return str(report_path)


def _run_learning_updates():
    updates = {
        "calibration": False,
        "history": False,
    }

    try:
        from skills.heuristics_calibration import analyze, load_json, RESULTS_PATH, SUMMARY_PATH, save_analysis

        calibration = analyze(
            load_json(RESULTS_PATH),
            load_json(SUMMARY_PATH),
        )
        save_analysis(calibration)
        updates["calibration"] = True
    except Exception:
        LOGGER.exception("learning update failed")

    try:
        from skills.heuristics_history import append_snapshot

        append_snapshot()
        updates["history"] = True
    except Exception:
        LOGGER.exception("learning update failed")

    return updates


def orchestrate(url, html=None, dry_run=True):
    initial_audit = run_audit(url, html=html)
    initial_issues = initial_audit["issues"]
    execution_plan = run_architect(initial_issues)

    generated_patches = []
    execution_results = []

    for issue in initial_issues:
        coding_result = run_coding(issue)

        if not isinstance(coding_result, dict):
            LOGGER.warning("invalid coding_result type=%s", type(coding_result))
            continue

        if not coding_result.get("success", False):
            LOGGER.warning("coding_agent failed issue=%s", issue.get("type"))
            continue

        generated_patches.append(coding_result)

        patch_content = coding_result.get("patch", "")

        if not patch_content:
            LOGGER.warning("empty patch skipped issue=%s", issue.get("type"))
            continue

        executor_patch = {
            "file_path": coding_result.get("target_file", "simulation.html"),
            "content": patch_content,
        }
        execution_result = run_executor(executor_patch, dry_run=dry_run)
        execution_result["issue_type"] = issue.get("type")
        execution_results.append(execution_result)

    after_issues = simulate_after_issues(
        initial_issues,
        execution_results,
    )
    reaudit_report = run_reaudit(initial_issues, after_issues)
    learning_updates = _run_learning_updates()

    report = {
        "success": True,
        "initial_issues": initial_issues,
        "execution_plan": execution_plan,
        "generated_patches": generated_patches,
        "execution_results": execution_results,
        "reaudit_report": reaudit_report,
        "final_quality_score": reaudit_report.get(
            "quality_score_after",
            initial_audit["quality_score"],
        ),
        "learning_updates": learning_updates,
        "timestamp": datetime.now().isoformat(),
        "stats": {
            "issues_detected": len(initial_issues),
            "patches_generated": len(generated_patches),
            "patches_executed": len(execution_results),
            "dry_run": dry_run,
        },
    }
    save_orchestration_report(report)
    LOGGER.info(
        "orchestration complete url=%s issues=%s dry_run=%s",
        url,
        len(initial_issues),
        dry_run,
    )
    return report


def run(action="full_cycle", **kwargs):
    if action == "full_cycle":
        return orchestrate(
            url=kwargs.get("url", ""),
            html=kwargs.get("html"),
            dry_run=kwargs.get("dry_run", True),
        )

    if action == "audit_only":
        audit = run_audit(
            url=kwargs.get("url", ""),
            html=kwargs.get("html"),
        )
        return {
            "success": True,
            **audit,
        }

    if action == "plan_only":
        return run_architect(kwargs.get("issues", []))

    return {
        "success": False,
        "error": f"Action inconnue: {action}",
    }
