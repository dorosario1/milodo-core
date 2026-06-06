import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ORIGINAL_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Chaussures de Sport | Achetez en Ligne</title>
    <meta name="description" content="Découvrez notre large collection de chaussures de sport pour homme et femme. Livraison gratuite dès 50€ d'achat.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://www.example.com/chaussures-sport">
    <meta property="og:title" content="Chaussures de Sport | Achetez en Ligne">
    <meta property="og:description" content="Large collection de chaussures de sport. Livraison gratuite.">
    <meta property="og:url" content="https://www.example.com/chaussures-sport">
    <meta property="og:type" content="website">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Chaussures de Sport",
        "description": "Chaussures de sport confortables",
        "offers": {
            "@type": "Offer",
            "price": "89.99",
            "priceCurrency": "EUR"
        }
    }
    </script>
</head>
<body>
    <h1>Chaussures de Sport</h1>
    <p>Large collection de chaussures de sport pour homme et femme.</p>
    <img src="chaussure1.jpg">
    <img src="chaussure2.jpg" alt="">
    <a href="/promo">Cliquez ici</a>
    <a href="/nouveautes">Voir les nouveautés</a>
    <a href="/contact">Contactez-nous</a>
</body>
</html>"""


PATCHED_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Chaussures de Sport | Achetez en Ligne - Livraison 24h</title>
    <meta name="description" content="Découvrez notre large collection de chaussures de sport pour homme et femme. Livraison gratuite dès 50€ d'achat. Retour sous 30 jours.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://www.example.com/chaussures-sport">
    <meta property="og:title" content="Chaussures de Sport | Achetez en Ligne - Livraison 24h">
    <meta property="og:description" content="Large collection de chaussures de sport. Livraison gratuite et retour facile.">
    <meta property="og:url" content="https://www.example.com/chaussures-sport">
    <meta property="og:type" content="website">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Chaussures de Sport Premium",
        "description": "Chaussures de sport confortables et légères. Idéales pour la course à pied et le trail.",
        "offers": {
            "@type": "Offer",
            "price": "89.99",
            "priceCurrency": "EUR"
        }
    }
    </script>
</head>
<body>
    <h1>Chaussures de Sport Premium</h1>
    <p>Large collection de chaussures de sport pour homme et femme. Confort garantit.</p>
    <img src="chaussure1.jpg" alt="Chaussure de sport bleue - vue avant">
    <img src="chaussure2.jpg" alt="Chaussure de sport rouge - vue profil">
    <a href="/promo" title="Promotions chaussures de sport">Cliquez ici pour voir nos promos</a>
    <a href="/nouveautes" title="Nouveautés chaussures">Voir les nouveautés</a>
    <a href="/contact" title="Contactez notre équipe">Contactez-nous</a>
</body>
</html>"""


def test_orchestrator_real_patch():
    """
    Test complet :
    1. Audit de ORIGINAL_HTML
    2. Orchestrator.run_orchestrator()
    3. Vérification décision
    4. Affichage scores comparés
    """

    print("=" * 60)
    print("TEST ORCHESTRATOR — PATCH RÉEL")
    print("=" * 60)

    from skills.audit_engine import audit_html

    audit_before = audit_html(ORIGINAL_HTML)
    score_before = audit_before.get("score") or audit_before.get("global_score")
    print(f"\n Score AVANT patch : {score_before}")

    from skills.orchestrator import run_orchestrator

    result = run_orchestrator(
        original_html=ORIGINAL_HTML,
        patched_html=PATCHED_HTML,
        audit_before=audit_before,
    )

    print(f"\n Score APRÈS patch : {result['score_after']}")
    print(f" Delta : {result['score_delta']}")
    print(f" Comparaison : {result['score_comparison']}")
    print(f"\n✅ Accepté : {result['accepted']}")
    print(f" Rollback requis : {result['rollback_required']}")
    print(f" Raison : {result['decision_reason']}")

    if result["error"]:
        print(f"❌ Erreur : {result['error']}")

    assert result["accepted"] is True, (
        f"Le patch aurait dû être accepté, raison: {result['decision_reason']}"
    )
    assert result["rollback_required"] is False
    assert result["score_after"] >= result["score_before"], (
        "Le score après patch devrait être >= score avant"
    )
    assert result["workspace_path"] is not None

    print(f"\n Workspace : {result['workspace_path']}")
    print("\n✅ TEST RÉUSSI — Le patch a été accepté avec amélioration du score.")

    return result


def test_orchestrator_degraded_patch():
    """
    Test avec un patch qui dégrade la page :
    - Suppression du title
    - Suppression meta description
    - Images sans alt
    - Liens cassés
    """

    bad_patch = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Chaussures</h1>
    <p>Achetez nos chaussures.</p>
    <img src="chaussure1.jpg">
    <a href="/promo">ici</a>
</body>
</html>"""

    from skills.audit_engine import audit_html
    from skills.orchestrator import run_orchestrator

    audit_before = audit_html(ORIGINAL_HTML)
    result = run_orchestrator(
        original_html=ORIGINAL_HTML,
        patched_html=bad_patch,
        audit_before=audit_before,
    )

    print("\n" + "=" * 60)
    print("TEST ORCHESTRATOR — PATCH DÉGRADÉ")
    print("=" * 60)
    print(f" Score AVANT : {result['score_before']}")
    print(f" Score APRÈS : {result['score_after']}")
    print(f" Delta : {result['score_delta']}")
    print(f"✅ Accepté : {result['accepted']}")
    print(f" Rollback requis : {result['rollback_required']}")
    print(f" Raison : {result['decision_reason']}")

    assert result["accepted"] is False, "Le patch dégradé devrait être refusé"
    assert result["rollback_required"] is True, "Rollback devrait être demandé"

    print("\n✅ TEST RÉUSSI — Le patch dégradé a été correctement refusé.")
    return result


if __name__ == "__main__":
    print(" PHASE 1 — VALIDATION ORCHESTRATOR\n")

    result_ok = test_orchestrator_real_patch()
    result_bad = test_orchestrator_degraded_patch()

    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)
    print(f"✅ Patch correct  → accepté : {result_ok['accepted']}")
    print(f"✅ Patch dégradé  → rollback : {result_bad['rollback_required']}")
    print("\n Moteur décisionnel validé.")
