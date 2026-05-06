from pathlib import Path


OUTPUT_DIR = Path("business_outputs")


def ensure_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)


def write_file(path, content):
    path.write_text(content, encoding="utf-8")
    return str(path)


def create_landing_page():
    ensure_output_dir()
    html = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offre exclusive MILODO</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; color: #111827; background: #f8fafc; }
    main { max-width: 920px; margin: 0 auto; padding: 48px 20px; }
    section { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 28px; }
    h1 { font-size: 42px; margin: 0 0 12px; }
    p { font-size: 18px; line-height: 1.5; }
    .cta { display: inline-block; margin-top: 18px; padding: 14px 20px; color: #ffffff; background: #16a34a; border-radius: 6px; text-decoration: none; font-weight: 700; }
  </style>
</head>
<body>
  <main>
    <section>
      <h1>Offre limitée pour passer à l'action</h1>
      <p>Une solution simple, rapide et optimisée pour convertir les visiteurs en acheteurs.</p>
      <p>Avantage clair, preuve immédiate, achat sans friction.</p>
      <a class="cta" href="#">Profiter de l'offre</a>
    </section>
  </main>
</body>
</html>
"""
    files = [write_file(OUTPUT_DIR / "landing_page.html", html)]
    print("[AGENT] landing page saved")
    return {
        "success": True,
        "action": "landing_page",
        "files": files,
        "errors": [],
    }


def create_email_sequence():
    ensure_output_dir()
    emails = """EMAIL 1 - Découverte
Objet: Une offre simple pour démarrer aujourd'hui
Corps: Voici une solution claire pour obtenir un résultat rapide.

EMAIL 2 - Preuve
Objet: Pourquoi cette offre fonctionne
Corps: Elle réduit la friction, clarifie la valeur et pousse à l'action.

EMAIL 3 - Urgence
Objet: Dernière chance avant fermeture
Corps: L'offre est limitée. Passe à l'action maintenant.
"""
    files = [write_file(OUTPUT_DIR / "email_sequence.txt", emails)]
    print("[AGENT] email sequence saved")
    return {
        "success": True,
        "action": "email_sequence",
        "files": files,
        "errors": [],
    }
