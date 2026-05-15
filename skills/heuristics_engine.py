from skills.html_extractors import extract_buttons, extract_forms, extract_whatsapp, extract_trust_elements, extract_urgency


def analyze(html, url=""):
    issues = []

    buttons = extract_buttons(html)
    if len(buttons) < 3:
        issues.append({
            "id": "cta_low",
            "type": "cta_weak",
            "severity": "medium",
            "confidence": 0.75,
            "zone": "general",
            "description": f"Seulement {len(buttons)} CTA detectes."
        })

    wa = extract_whatsapp(html)
    if not wa:
        issues.append({
            "id": "no_whatsapp",
            "type": "missing_contact",
            "severity": "medium",
            "confidence": 0.85,
            "zone": "contact",
            "description": "Aucun lien WhatsApp."
        })

    forms = extract_forms(html)
    if forms:
        for form in forms:
            if "réponse" not in form.lower() and "2h" not in form.lower() and "rapide" not in form.lower():
                issues.append({
                    "id": "form_no_trust",
                    "type": "trust_missing",
                    "severity": "low",
                    "confidence": 0.60,
                    "zone": "contact",
                    "description": "Formulaire sans delai de reponse."
                })
                break

    trust = extract_trust_elements(html)
    if not trust:
        issues.append({
            "id": "no_trust",
            "type": "trust_missing",
            "severity": "high",
            "confidence": 0.80,
            "zone": "general",
            "description": "Aucun element de confiance."
        })

    urgency = extract_urgency(html)
    if not urgency:
        issues.append({
            "id": "no_urgency",
            "type": "conversion_weak",
            "severity": "low",
            "confidence": 0.55,
            "zone": "general",
            "description": "Aucun element d'urgence."
        })

    return {
        "success": True,
        "url": url,
        "issues": issues,
        "summary": {
            "critical": len([i for i in issues if i["severity"] == "critical"]),
            "high": len([i for i in issues if i["severity"] == "high"]),
            "medium": len([i for i in issues if i["severity"] == "medium"]),
            "low": len([i for i in issues if i["severity"] == "low"]),
            "total": len(issues)
        }
    }
