import re

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
            "file": url,
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
            "file": url,
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
                    "file": url,
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
            "file": url,
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
            "file": url,
            "description": "Aucun element d'urgence."
        })

    # 6. SEO - Title
    title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    if not title_match:
        issues.append({
            "id": "no_title", "type": "seo_missing", "severity": "high",
            "confidence": 0.95, "zone": "head", "file": url,
            "description": "Balise title absente. Critique pour le SEO."
        })
    elif len(title_match.group(1).strip()) < 10:
        issues.append({
            "id": "short_title", "type": "seo_weak", "severity": "medium",
            "confidence": 0.80, "zone": "head", "file": url,
            "description": f"Title trop court ({len(title_match.group(1))} chars). Visez 50-60 caracteres."
        })

    # 7. SEO - Meta description
    meta_desc = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.IGNORECASE)
    if not meta_desc:
        issues.append({
            "id": "no_meta_desc", "type": "seo_missing", "severity": "medium",
            "confidence": 0.85, "zone": "head", "file": url,
            "description": "Meta description absente. Important pour le CTR dans Google."
        })

    # 8. Hero - H1
    h1_count = len(re.findall(r'<h1[^>]*>', html, re.IGNORECASE))
    if h1_count == 0:
        issues.append({
            "id": "no_h1", "type": "hero_weak", "severity": "high",
            "confidence": 0.85, "zone": "hero", "file": url,
            "description": "Aucune balise H1. Importance SEO et clarte du message."
        })
    elif h1_count > 1:
        issues.append({
            "id": "multiple_h1", "type": "seo_weak", "severity": "low",
            "confidence": 0.70, "zone": "hero", "file": url,
            "description": f"Plusieurs H1 ({h1_count}). Un seul H1 recommande."
        })

    # 9. Images - alt
    images = re.findall(r'<img[^>]*>', html, re.IGNORECASE)
    images_without_alt = [img for img in images if 'alt=' not in img]
    if len(images) > 0 and len(images_without_alt) / len(images) > 0.5:
        issues.append({
            "id": "missing_alt", "type": "accessibility", "severity": "low",
            "confidence": 0.75, "zone": "general", "file": url,
            "description": f"{len(images_without_alt)}/{len(images)} images sans attribut alt."
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
