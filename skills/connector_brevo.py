import os
import json
import urllib.request
import urllib.error


def _is_configured() -> bool:
    return all(
        os.environ.get(v)
        for v in (
            "MILODO_BREVO_API_KEY",
            "MILODO_BREVO_SENDER",
            "MILODO_BREVO_RECIPIENT",
        )
    )


def _build_issues_html(
    audit_before: dict = None,
) -> str:
    """Generate HTML list of issues."""

    if not audit_before:
        return (
            "<ul>"
            "<li>✅ Corrections automatiques appliquées</li>"
            "</ul>"
        )

    issues = audit_before.get("issues", [])

    if issues:
        items = "".join(
            f"<li>✅ {issue}</li>"
            for issue in issues[:10]
        )

        return (
            "<ul style='color:#c9d1d9;'>"
            f"{items}"
            "</ul>"
        )

    return (
        "<ul>"
        "<li>✅ Corrections automatiques appliquées</li>"
        "</ul>"
    )


def _build_subject(
    result: dict,
) -> str:
    """Build email subject."""

    initial = result.get("initial_score", "?")
    final = result.get("final_score", "?")
    improvement = result.get("improvement", 0)

    if result.get("rollback_triggered"):
        return (
            f"⚠️ MILODO Rollback : "
            f"{initial} → {final} "
            f"({improvement:+.1f})"
        )

    if result.get("converged"):
        return (
            f"✅ MILODO Auto-Correction : "
            f"{initial} → {final} "
            f"(+{improvement})"
        )

    return (
        f" MILODO Auto-Correction : "
        f"{initial} → {final} "
        f"(+{improvement})"
    )


def _build_email_html(
    original_html: str,
    result: dict,
    audit_before: dict = None,
) -> str:
    """Build Brevo HTML email."""

    initial = result.get("initial_score", "?")
    final = result.get("final_score", "?")
    improvement = result.get("improvement", 0)
    iterations = result.get("iterations_count", 0)

    converged = (
        "✅ Oui"
        if result.get("converged")
        else "❌ Non"
    )

    rollback = (
        "⚠️ Oui"
        if result.get("rollback_triggered")
        else "Non"
    )

    improvement_color = (
        "#3fb950"
        if improvement >= 0
        else "#f85149"
    )

    issues_html = _build_issues_html(
        audit_before
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>

<body style="font-family:system-ui,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px;max-width:600px;">

<h1 style="color:#3fb950;">
✅ MILODO Auto-Correction
</h1>

<table style="width:100%;border-collapse:collapse;margin:20px 0;">

<tr style="background:#161b22;">
<td style="padding:12px;border:1px solid #30363d;">
 Score initial
</td>
<td style="padding:12px;border:1px solid #30363d;font-weight:bold;">
{initial}
</td>
</tr>

<tr style="background:#161b22;">
<td style="padding:12px;border:1px solid #30363d;">
 Score final
</td>
<td style="padding:12px;border:1px solid #30363d;font-weight:bold;color:#3fb950;">
{final}
</td>
</tr>

<tr style="background:#161b22;">
<td style="padding:12px;border:1px solid #30363d;">
 Amélioration
</td>
<td style="padding:12px;border:1px solid #30363d;font-weight:bold;color:{improvement_color};">
{improvement}
</td>
</tr>

<tr style="background:#161b22;">
<td style="padding:12px;border:1px solid #30363d;">
 Itérations
</td>
<td style="padding:12px;border:1px solid #30363d;">
{iterations}
</td>
</tr>

<tr style="background:#161b22;">
<td style="padding:12px;border:1px solid #30363d;">
 Convergé
</td>
<td style="padding:12px;border:1px solid #30363d;color:#3fb950;">
{converged}
</td>
</tr>

<tr style="background:#161b22;">
<td style="padding:12px;border:1px solid #30363d;">
️ Rollback
</td>
<td style="padding:12px;border:1px solid #30363d;">
{rollback}
</td>
</tr>

</table>

<h2 style="color:#58a6ff;">
 Issues corrigées
</h2>

{issues_html}

<hr style="border-color:#30363d;margin:20px 0;">

<p style="color:#8b949e;font-size:12px;">
⚡ Rapport automatique MILODO
</p>

</body>
</html>"""


def _send_brevo_email(
    subject: str,
    html_content: str,
) -> dict:
    """Send email through Brevo API."""

    api_key = os.environ[
        "MILODO_BREVO_API_KEY"
    ]

    sender = os.environ[
        "MILODO_BREVO_SENDER"
    ]

    recipient = os.environ[
        "MILODO_BREVO_RECIPIENT"
    ]

    url = (
        "https://api.brevo.com/"
        "v3/smtp/email"
    )

    payload = json.dumps({
        "sender": {
            "name": "MILODO Bot",
            "email": sender,
        },
        "to": [
            {
                "email": recipient,
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
    }).encode("utf-8")

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=10,
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

            return {
                "sent": True,
                "error": None,
                "config_missing": False,
                "message_id": data.get(
                    "messageId"
                ),
            }

    except urllib.error.HTTPError as e:

        try:
            error_body = (
                e.read().decode("utf-8")
                if e.fp
                else str(e)
            )
        except Exception:
            error_body = str(e)

        return {
            "sent": False,
            "error": error_body,
            "config_missing": False,
            "message_id": None,
        }

    except Exception as e:

        return {
            "sent": False,
            "error": str(e),
            "config_missing": False,
            "message_id": None,
        }


def send_autocorrect_email(
    original_html: str,
    result: dict,
    audit_before: dict = None,
) -> dict:
    """
    Send MILODO auto-correction email.
    Never crash the core flow.
    """

    if not _is_configured():

        return {
            "sent": False,
            "error": None,
            "config_missing": True,
            "message_id": None,
        }

    try:

        subject = _build_subject(result)

        html_content = _build_email_html(
            original_html,
            result,
            audit_before,
        )

        return _send_brevo_email(
            subject,
            html_content,
        )

    except Exception as e:

        return {
            "sent": False,
            "error": str(e),
            "config_missing": False,
            "message_id": None,
        }
