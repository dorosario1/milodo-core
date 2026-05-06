from pathlib import Path


OUTPUT_DIR = Path("business_outputs")


def ensure_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)


def write_file(path, content):
    path.write_text(content, encoding="utf-8")
    return str(path)


def generate_tiktok_content():
    return (
        "Hook: Tu peux transformer ton quotidien en 30 secondes.\n"
        "Script: Montre le problème, révèle le produit, affiche le résultat.\n"
        "CTA: Commente MILODO pour recevoir l'offre."
    )


def generate_whatsapp_content():
    return (
        "Message viral WhatsApp:\n"
        "Nouvelle offre exclusive aujourd'hui. Réponds OUI pour recevoir le lien avant expiration."
    )


def generate_instagram_content():
    return (
        "Caption Instagram:\n"
        "Passe à l'action maintenant. Offre limitée, résultat visible, achat simple.\n"
        "Hashtags: #offre #fitness #shopping #milodo"
    )


def generate_traffic_content():
    ensure_output_dir()
    files = [
        write_file(OUTPUT_DIR / "tiktok_content.txt", generate_tiktok_content()),
        write_file(OUTPUT_DIR / "whatsapp_traffic.txt", generate_whatsapp_content()),
        write_file(OUTPUT_DIR / "instagram_content.txt", generate_instagram_content()),
    ]
    print("[AGENT] traffic content saved")
    return {
        "success": True,
        "action": "traffic",
        "files": files,
        "errors": [],
    }


def generate_whatsapp_scripts():
    ensure_output_dir()
    scripts = {
        "initial": "Salut, j'ai une offre qui peut t'intéresser aujourd'hui. Tu veux le lien ?",
        "follow_up": "Je te relance vite: l'offre est encore disponible, mais pas pour longtemps.",
        "closing": "Dernière étape: confirme maintenant et je t'envoie l'accès direct.",
        "abandoned_cart": "Tu as laissé ton panier ouvert. Je peux te renvoyer le lien pour finaliser.",
    }
    content = "\n\n".join(f"{name.upper()}\n{text}" for name, text in scripts.items())
    files = [write_file(OUTPUT_DIR / "whatsapp_sales_scripts.txt", content)]
    print("[AGENT] WhatsApp scripts saved")
    return {
        "success": True,
        "action": "sales",
        "files": files,
        "errors": [],
    }
