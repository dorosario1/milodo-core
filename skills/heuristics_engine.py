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

    # 10. WhatsApp - Bouton flottant
    has_wa_link = bool(re.search(r'(?:wa\.me|api\.whatsapp\.com|whatsapp://)', html, re.IGNORECASE))
    has_floating_wa = bool(re.search(r'(?:position:\s*fixed|position:fixed).*(?:whatsapp|wa\.me)', html, re.IGNORECASE | re.DOTALL))
    whatsapp_above_fold = bool(re.search(r'<(?:header|nav|section)[^>]*>.*?(?:wa\.me|whatsapp).*?</(?:header|nav|section)>', html, re.IGNORECASE | re.DOTALL))

    if not has_wa_link:
        # Déjà couvert par missing_contact plus haut, on ajoute juste la spécificité WhatsApp
        pass
    elif has_wa_link and not has_floating_wa:
        issues.append({
            "id": "whatsapp_not_floating",
            "type": "whatsapp_ux",
            "severity": "low",
            "confidence": 0.65,
            "zone": "contact",
            "file": url,
            "description": "WhatsApp present mais pas en bouton flottant. Meilleure conversion avec un bouton fixe mobile."
        })

    if has_wa_link and not whatsapp_above_fold:
        issues.append({
            "id": "whatsapp_below_fold",
            "type": "whatsapp_ux",
            "severity": "medium",
            "confidence": 0.70,
            "zone": "contact",
            "file": url,
            "description": "WhatsApp non visible immediatement (below the fold). Impact conversion mobile."
        })

    # 11. WhatsApp - Qualité du message
    wa_messages = re.findall(r'(?:wa\.me|whatsapp.*?)(?:text|message)[^"]*"?([^"]*)"?', html, re.IGNORECASE)
    if has_wa_link and wa_messages:
        for msg in wa_messages:
            if len(msg.strip()) < 10:
                issues.append({
                    "id": "whatsapp_weak_message",
                    "type": "whatsapp_ux",
                    "severity": "low",
                    "confidence": 0.60,
                    "zone": "contact",
                    "file": url,
                    "description": "Message WhatsApp pre-rempli trop court. Ajouter un message clair ameliore la conversion."
                })
                break

    # 12. Navigation - Nombre de liens
    nav_links = re.findall(r'<nav[^>]*>.*?</nav>', html, re.DOTALL | re.IGNORECASE)
    if nav_links:
        for nav in nav_links:
            links = re.findall(r'<a[^>]+href="([^"]*)"[^>]*>', nav, re.IGNORECASE)
            if len(links) > 15:
                issues.append({
                    "id": "nav_too_many_links",
                    "type": "navigation_ux",
                    "severity": "low",
                    "confidence": 0.65,
                    "zone": "navigation",
                    "file": url,
                    "description": f"Navigation contient {len(links)} liens. Trop de choix reduit la clarte."
                })
                break
    else:
        issues.append({
            "id": "no_nav",
            "type": "navigation_missing",
            "severity": "medium",
            "confidence": 0.75,
            "zone": "navigation",
            "file": url,
            "description": "Aucune balise <nav> detectee. Structure de navigation absente."
        })

    # 13. Formulaires - Nombre de champs
    forms_html = re.findall(r'<form[^>]*>(.*?)</form>', html, re.DOTALL | re.IGNORECASE)
    for form in forms_html:
        inputs = re.findall(r'<(?:input|textarea|select)[^>]*>', form, re.IGNORECASE)
        if len(inputs) > 6:
            issues.append({
                "id": "form_too_long",
                "type": "form_friction",
                "severity": "medium",
                "confidence": 0.70,
                "zone": "contact",
                "file": url,
                "description": f"Formulaire avec {len(inputs)} champs. Reduire pour augmenter la conversion."
            })
            break

        if 'placeholder' not in form.lower():
            issues.append({
                "id": "form_no_placeholder",
                "type": "form_friction",
                "severity": "low",
                "confidence": 0.55,
                "zone": "contact",
                "file": url,
                "description": "Formulaire sans attributs placeholder. L'UX mobile en patit."
            })
            break

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
