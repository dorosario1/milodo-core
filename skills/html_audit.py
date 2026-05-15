SKILL_NAME = "html_audit"
SKILL_DESCRIPTION = "Audite une page web via son URL et détecte les problèmes UI"
SKILL_VERSION = "1.0.0"

import urllib.request
import re
from skills.html_extractors import extract_buttons, extract_forms, extract_whatsapp, extract_trust_elements, extract_urgency, quick_stats


class HTMLAuditor:
    def audit_url(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MILODO-HTMLAudit/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
            try:
                html = raw.decode("utf-8")
            except:
                html = raw.decode("latin-1", errors="replace")
        except Exception as e:
            return {"success": False, "error": str(e)}

        issues = []

        # 1. CTA faibles
        buttons = extract_buttons(html)

        if len(buttons) < 3:
            issues.append({
                "id": "cta_count",
                "type": "cta_weak",
                "severity": "medium",
                "confidence": 0.70,
                "zone": "general",
                "description": f"Peu de CTA visibles ({len(buttons)}). Ajouter des boutons d'action."
            })

        # 2. WhatsApp manquant
        wa_links = extract_whatsapp(html)
        if not wa_links:
            issues.append({
                "id": "no_whatsapp",
                "type": "missing_contact",
                "severity": "medium",
                "confidence": 0.80,
                "zone": "contact",
                "description": "Pas de lien WhatsApp détecté. Crucial pour le tourisme."
            })

        # 3. Formulaire sans réassurance
        if "<form" in html.lower() and "réponse" not in html.lower() and "2h" not in html.lower():
            issues.append({
                "id": "form_no_trust",
                "type": "trust_missing",
                "severity": "low",
                "confidence": 0.60,
                "zone": "contact",
                "description": "Formulaire sans mention de délai de réponse."
            })

        # 4. Pas d'urgence
        urgency = extract_urgency(html)
        trust = extract_trust_elements(html)
        if not urgency:
            issues.append({
                "id": "no_urgency",
                "type": "conversion_weak",
                "severity": "low",
                "confidence": 0.55,
                "zone": "general",
                "description": "Aucun élément d'urgence ou de rareté."
            })

        # 5. Titre
        title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1) if title_match else "N/A"

        return {
            "success": True,
            "url": url,
            "title": title,
            "issues": issues,
            "quick_stats": quick_stats(html),
            "summary": {
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "medium": len([i for i in issues if i["severity"] == "medium"]),
                "low": len([i for i in issues if i["severity"] == "low"]),
                "total": len(issues)
            }
        }


def run(action="audit_url", **kwargs):
    auditor = HTMLAuditor()
    if action == "audit_url":
        url = kwargs.get("url", "")
        return auditor.audit_url(url)
    return {"success": False, "error": f"Action inconnue: {action}"}
