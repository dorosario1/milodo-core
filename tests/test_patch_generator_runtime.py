import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ORIGINAL_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Chaussures</title>
    <meta name="description" content="Découvrez notre sélection de chaussures de sport pour homme et femme.">
    <link rel="canonical" href="https://example.com/chaussures">
    <meta property="og:title" content="Chaussures">
    <meta property="og:description" content="Sélection de chaussures de sport.">
    <meta property="og:url" content="https://example.com/chaussures">
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Chaussures"}
    </script>
</head>
<body>
    <h1>Chaussures de sport</h1>
    <img src="shoe-1.jpg">
    <a href="/promo">Cliquez ici</a>
</body>
</html>"""


def test_patch_generator_runtime():
    from skills.audit_engine import audit_html
    from skills.patch_generator import generate_patched_html
    from skills.orchestrator import run_orchestrator

    audit_before = audit_html(ORIGINAL_HTML)
    patched_html = generate_patched_html(ORIGINAL_HTML, audit_before)
    result = run_orchestrator(
        original_html=ORIGINAL_HTML,
        patched_html=patched_html,
        audit_before=audit_before,
    )

    assert patched_html != ORIGINAL_HTML
    assert result["score_after"] >= result["score_before"]
    assert result["accepted"] is True
    assert result["rollback_required"] is False

    print("PHASE4_PATCH_GENERATOR_OK")


if __name__ == "__main__":
    test_patch_generator_runtime()
