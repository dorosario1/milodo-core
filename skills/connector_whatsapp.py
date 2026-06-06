import os
import json
import urllib.request
import urllib.error
from datetime import datetime


def _is_configured() -> bool:
    return all(
        os.environ.get(var)
        for var in (
            "MILODO_WHATSAPP_TOKEN",
            "MILODO_WHATSAPP_PHONE_ID",
            "MILODO_WHATSAPP_RECIPIENT",
        )
    )


def _extract_issues(
    original_html: str,
    result: dict,
) -> str:
    """
    Build a short human-readable issues summary.
    """

    issues = []

    html_lower = original_html.lower()

    if "<title>" not in html_lower:
        issues.append("• Title ajouté")
    else:
        issues.append("• Title enrichi")

    if 'meta name="description"' not in html_lower:
        issues.append("• Meta description ajoutée")

    if "alt=" not in html_lower:
        issues.append("• Images avec alt")

    generic_links = (
        "cliquez ici",
        ">ici<",
        "click here",
        ">here<",
    )

    if any(link in html_lower for link in generic_links):
        issues.append("• Liens descriptifs")

    if "og:" not in html_lower:
        issues.append("• Open Graph complété")

    if "application/ld+json" not in html_lower:
        issues.append("• JSON-LD ajouté")

    if not issues:
        issues.append("• Optimisations automatiques")

    return "\n".join(issues[:6])


def _build_message(
    original_html: str,
    result: dict,
) -> str:
    initial = result.get("initial_score", "?")
    final = result.get("final_score", "?")
    improvement = result.get("improvement", 0)
    iterations = result.get("iterations_count", 0)

    converged = (
        "Oui"
        if result.get("converged")
        else "Non"
    )

    rollback = (
        "Oui"
        if result.get("rollback_triggered")
        else "Non"
    )

    issues_text = _extract_issues(
        original_html,
        result,
    )

    message = (
        f"✅ *MILODO Auto-Correction*\n\n"
        f" Score : {initial} → {final} (+{improvement})\n"
        f" Itérations : {iterations}\n"
        f" Convergé : {converged}\n"
        f"️ Rollback : {rollback}\n\n"
        f" Issues corrigées :\n"
        f"{issues_text}\n\n"
        f"⚡ _Rapport automatique MILODO_"
    )

    if len(message) > 1000:
        message = message[:997] + "..."

    return message


def _send_whatsapp_message(
    message: str,
) -> dict:
    token = os.environ[
        "MILODO_WHATSAPP_TOKEN"
    ]

    phone_id = os.environ[
        "MILODO_WHATSAPP_PHONE_ID"
    ]

    recipient = os.environ[
        "MILODO_WHATSAPP_RECIPIENT"
    ]

    url = (
        "https://graph.facebook.com/"
        f"v21.0/{phone_id}/messages"
    )

    payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message,
        },
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
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

            response_data = json.loads(
                response.read().decode("utf-8")
            )

            return {
                "sent": True,
                "error": None,
                "config_missing": False,
                "response": response_data,
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
            "response": None,
        }

    except Exception as e:

        return {
            "sent": False,
            "error": str(e),
            "config_missing": False,
            "response": None,
        }


def send_autocorrect_report(
    original_html: str,
    result: dict,
) -> dict:
    """
    Send WhatsApp report.
    Never crash the main MILODO flow.
    """

    if not _is_configured():

        return {
            "sent": False,
            "error": None,
            "config_missing": True,
            "response": None,
        }

    try:
        message = _build_message(
            original_html,
            result,
        )

        return _send_whatsapp_message(message)

    except Exception as e:

        return {
            "sent": False,
            "error": str(e),
            "config_missing": False,
            "response": None,
        }
