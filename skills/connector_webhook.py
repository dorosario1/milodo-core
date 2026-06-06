import os
import json
import urllib.request
import urllib.error
from datetime import datetime


def _build_event_payload(
    result: dict,
    audit_before: dict = None,
    workspace_name: str = None,
    duration_ms: int = None,
) -> dict:
    """Build standardized MILODO event payload."""

    issues = []

    if audit_before:
        issues = audit_before.get("issues", [])

    return {
        "event": "autocorrect.completed",
        "timestamp": datetime.now().isoformat(),
        "service": "MILODO",
        "version": "1.0.0",
        "data": {
            "initial_score": result.get(
                "initial_score"
            ),
            "final_score": result.get(
                "final_score"
            ),
            "improvement": result.get(
                "improvement"
            ),
            "iterations": result.get(
                "iterations_count"
            ),
            "converged": result.get(
                "converged"
            ),
            "rollback_triggered": result.get(
                "rollback_triggered"
            ),
            "issues_count": len(issues),
            "issues": issues[:20],
            "workspace_name": workspace_name,
            "duration_ms": duration_ms,
        },
    }


def _post_to_url(
    url: str,
    payload: dict,
    timeout: int = 5,
) -> dict:
    """
    POST payload to a single URL.
    Never raise exceptions.
    """

    data = json.dumps(payload).encode(
        "utf-8"
    )

    headers = {
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=timeout,
        ) as response:

            return {
                "url": url,
                "success": True,
                "status": response.status,
                "error": None,
            }

    except urllib.error.HTTPError as e:

        return {
            "url": url,
            "success": False,
            "status": e.code,
            "error": (
                f"HTTP {e.code}: "
                f"{e.reason}"
            ),
        }

    except Exception as e:

        return {
            "url": url,
            "success": False,
            "status": None,
            "error": str(e)[:200],
        }


def dispatch_autocorrect_event(
    result: dict,
    audit_before: dict = None,
    workspace_name: str = None,
    duration_ms: int = None,
) -> dict:
    """
    Dispatch event to all configured URLs.
    Never crash the MILODO flow.
    """

    urls_env = os.environ.get(
        "MILODO_WEBHOOK_URLS",
        "",
    ).strip()

    if not urls_env:

        return {
            "dispatched": False,
            "urls_total": 0,
            "urls_success": 0,
            "urls_failed": 0,
            "config_missing": True,
            "results": [],
        }

    urls = [
        u.strip()
        for u in urls_env.split(",")
        if u.strip()
    ]

    if not urls:

        return {
            "dispatched": False,
            "urls_total": 0,
            "urls_success": 0,
            "urls_failed": 0,
            "config_missing": True,
            "results": [],
        }

    payload = _build_event_payload(
        result,
        audit_before,
        workspace_name,
        duration_ms,
    )

    results = []

    success_count = 0
    failed_count = 0

    for url in urls:

        res = _post_to_url(
            url,
            payload,
        )

        results.append(res)

        if res["success"]:
            success_count += 1
        else:
            failed_count += 1

    return {
        "dispatched": True,
        "urls_total": len(urls),
        "urls_success": success_count,
        "urls_failed": failed_count,
        "config_missing": False,
        "results": results,
    }
