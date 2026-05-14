SKILL_NAME = "intent_detector"
SKILL_DESCRIPTION = "Détecte l'intention utilisateur et la traduit en workflow technique"
SKILL_VERSION = "1.0.0"

import re


INTENTS = {
    "shopify_audit": {
        "keywords": ["améliore", "optimise", "audite", "vérifie", "corrige", "fix"],
        "domains": ["shopify", "dofitpro", "boutique", "store", "thème", "theme"],
        "prompt_template": "Analyse le thème Shopify {project}. Détecte les problèmes UI : header, contraste, padding, CTA, mobile. Propose des correctifs.",
        "skill": "shopify_audit"
    },
    "fix_ui": {
        "keywords": ["corrige", "répare", "fix", "header", "bande blanche", "padding", "contraste"],
        "domains": ["shopify", "dofitpro", "site", "page"],
        "prompt_template": "Corrige le problème UI suivant sur {project} : {detail}. Propose un patch Liquid/CSS.",
        "skill": "shopify_audit"
    },
    "mobile_audit": {
        "keywords": ["mobile", "responsive", "téléphone", "smartphone"],
        "domains": ["shopify", "dofitpro", "site", "page"],
        "prompt_template": "Audite la version mobile de {project}. Vérifie : lisibilité, CTA, spacing, overflow horizontal.",
        "skill": "shopify_audit"
    },
    "optimize_conversion": {
        "keywords": ["conversion", "ventes", "cro", "taux", "achat", "vendre"],
        "domains": ["shopify", "dofitpro", "boutique", "store"],
        "prompt_template": "Analyse les pages produits de {project}. Optimise : titre, description, CTA, preuve sociale, images.",
        "skill": "shopify_audit"
    }
}


def detect_intent(message, context=None):
    """
    Détecte l'intention à partir du message utilisateur.
    Retourne {
        "intent": "shopify_audit",
        "confidence": 0.8,
        "project": "dofitpro",
        "prompt": "...",
        "skill": "shopify_audit"
    }
    """
    message_lower = message.lower()

    best_intent = None
    best_score = 0

    for intent_name, intent_data in INTENTS.items():
        keyword_score = sum(1 for kw in intent_data["keywords"] if kw in message_lower)
        domain_score = sum(1 for d in intent_data["domains"] if d in message_lower)
        total_score = keyword_score + domain_score

        if total_score > best_score:
            best_score = total_score
            best_intent = intent_name

    if best_intent and best_score > 0:
        intent_data = INTENTS[best_intent]
        project = _extract_project(message_lower) or (context.get("project") if context else "dofitpro")
        detail = _extract_detail(message_lower)

        prompt = intent_data["prompt_template"].format(project=project, detail=detail or "")

        return {
            "intent": best_intent,
            "confidence": min(best_score / 5, 1.0),
            "project": project,
            "prompt": prompt,
            "skill": intent_data["skill"]
        }

    return None


def _extract_project(text):
    projects = ["dofitpro", "kedougou", "casamance", "immo"]
    for p in projects:
        if p in text:
            return p
    return None


def _extract_detail(text):
    details = ["header", "bande blanche", "contraste", "padding", "cta", "bouton", "mobile", "hero"]
    found = [d for d in details if d in text]
    return ", ".join(found) if found else None


def run(action="detect", **kwargs):
    if action == "detect":
        message = kwargs.get("message", "")
        context = kwargs.get("context", None)
        return detect_intent(message, context)
    else:
        return {"success": False, "error": f"Action inconnue: {action}"}
