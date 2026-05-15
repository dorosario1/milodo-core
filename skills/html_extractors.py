import re


def extract_buttons(html):
    buttons = []
    buttons += re.findall(r'<a[^>]*class="[^"]*(?:btn|button|cta)[^"]*"[^>]*>([^<]+)</a>', html, re.IGNORECASE)
    buttons += re.findall(r'<button[^>]*>([^<]+)</button>', html, re.IGNORECASE)
    buttons += re.findall(r'<a[^>]*>[^<]*(?:réserver|contact|devis|réservation|découvrir|voir|commander|acheter|essayer)[^<]*</a>', html, re.IGNORECASE)
    return list(set(buttons))


def extract_forms(html):
    return re.findall(r'<form[^>]*>(.*?)</form>', html, re.DOTALL | re.IGNORECASE)


def extract_whatsapp(html):
    return re.findall(r'href="(https?://wa\.me/\d+[^"]*)"', html, re.IGNORECASE)


def extract_nav_links(html):
    nav = re.search(r'<nav[^>]*>(.*?)</nav>', html, re.DOTALL | re.IGNORECASE)
    return re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', nav.group(1), re.IGNORECASE) if nav else []


def extract_sections(html):
    return re.findall(r'<(?:section|div)[^>]*(?:id|class)="[^"]*([^"]*section[^"]*|hero|header|footer|main|content)[^"]*"[^>]*>', html, re.IGNORECASE)


def extract_trust_elements(html):
    trust = []
    if re.search(r'(?:avis|témoignage|temoignage|review|note|étoile|trustpilot)', html, re.IGNORECASE):
        trust.append("reviews")
    if re.search(r'(?:garanti|satisfait|remboursé|rembourse|paiement sécurisé|secure)', html, re.IGNORECASE):
        trust.append("guarantee")
    return trust


def extract_urgency(html):
    return ["scarcity"] if re.search(r'(?:place limitée|limité|dernière|urgence|bientôt|expire|offre spéciale)', html, re.IGNORECASE) else []


def quick_stats(html):
    return {
        "buttons": len(extract_buttons(html)),
        "forms": len(extract_forms(html)),
        "whatsapp": len(extract_whatsapp(html)),
        "nav_links": len(extract_nav_links(html)),
        "trust": len(extract_trust_elements(html)),
        "urgency": len(extract_urgency(html))
    }
