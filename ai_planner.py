"""
MILODO AI Planner — Phase 2 (V1 Rules-Based)

Rôle:
- Interpréter une phrase utilisateur
- Produire une commande canonique sûre
- Servir de couche d’intelligence entre CLI et système

Pipeline cible:

    user_input
    → ai_plan()
    → command canonique
    → map_command()
    → planner()
    → DAG
    → SQLite

Responsabilités:

- Détection d’intention:
    deploy
    build
    test
    healthcheck

- Normalisation:
    "deploy my app"
    → "deploy"

- Sécurité:
    refuse toute commande inconnue ou dangereuse

---

Retour standard:

{
    "intent": str,
    "target": str | None,
    "command": str | None,
    "confidence": float,
    "reason": str,
    "safe": bool
}

---

Règles de sécurité:

- confidence < 0.7 → safe=False
- commande inconnue → safe=False
- mots dangereux → safe=False

Exemples refusés:

    rm -rf /
    delete all
    shutdown system

---

Comportement:

- Ne déclenche aucune exécution
- Ne dépend d’aucun module externe
- Ne modifie pas le DAG
- Ne modifie pas SQLite

---

Contraintes Phase 2:

- Pas d’Event Bus (sera ajouté après)
- Pas de Scheduler
- Pas de LLM externe
- Parser déterministe uniquement

---

Résultat:

    input flou → commande sûre et standardisée

---

Limites V1:

- Support limité aux intents définis
- Pas de compréhension contextuelle avancée

---

Évolution future:

- Intégration LLM (Phase 2 avancée)
- Multi-target
- Score dynamique basé historique
- Feedback loop via SQLite
"""


DANGEROUS_KEYWORDS = (
    "rm -rf",
    "format",
    "delete all",
    "shutdown",
    "wipe",
)


def _result(intent, target, command, confidence, reason):
    safe = bool(command) and confidence >= 0.7
    return {
        "intent": intent,
        "target": target,
        "command": command if safe else None,
        "confidence": confidence if safe else 0.0,
        "reason": reason,
        "safe": safe,
    }


def ai_plan(user_input: str) -> dict:
    text = str(user_input or "").strip().lower()

    if not text:
        return _result(None, None, None, 0.0, "empty input")

    for keyword in DANGEROUS_KEYWORDS:
        if keyword in text:
            return _result(None, None, None, 0.0, f"dangerous keyword detected: {keyword}")

    if "deploy" in text:
        return _result(
            "deploy",
            None,
            "deploy",
            0.95,
            "deploy intent detected",
        )

    if "build" in text:
        return _result("build", None, "build", 0.9, "build intent detected")

    if "test" in text:
        return _result("test", None, "test", 0.9, "test intent detected")

    if "healthcheck" in text or "health check" in text or "health" in text:
        return _result("healthcheck", None, "healthcheck", 0.9, "healthcheck intent detected")

    return _result(None, None, None, 0.0, "unknown intent")
