import re
from pathlib import Path


VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def validate_html(content):
    """
    Vérifie la structure HTML.
    Retourne {"valid": True/False, "errors": [...]}
    """
    text = str(content or "")
    errors = []

    if not re.search(r"<!DOCTYPE\s+html>", text, re.IGNORECASE):
        errors.append("DOCTYPE html manquant")

    if not re.search(r"<html\b", text, re.IGNORECASE):
        errors.append("Balise <html> manquante")

    if not re.search(r"<body\b", text, re.IGNORECASE):
        errors.append("Balise <body> manquante")

    malformed_tags = re.findall(r"</?[a-z]+[A-Z][A-Za-z0-9-]*\b[^>]*>", text)
    for tag in malformed_tags:
        errors.append(f"Balise mal formée : {tag}")

    tags = re.findall(r"<[^!/\s][^<>]*>", text)
    for tag in tags:
        clean_tag = re.sub(r'"[^"]*"|\'[^\']*\'', '""', tag)
        unquoted_attrs = re.findall(
            r"\s([A-Za-z_:][\w:.-]*)=([^\s\"'=<>`]+)",
            clean_tag,
        )

        for attr, value in unquoted_attrs:
            if attr == "viewBox" or attr == "xmlns":
                continue
            if attr.startswith("aria-") or attr.startswith("data-"):
                continue
            errors.append(f"Attribut sans guillemets : {attr}={value}")

    errors.extend(_find_unclosed_html_tags(text))

    return {
        "valid": not errors,
        "errors": errors,
    }


def validate_css(content):
    """
    Vérifie la syntaxe CSS basique.
    Retourne {"valid": True/False, "errors": [...]}
    """
    text = str(content or "")
    errors = []

    if text.count("{") != text.count("}"):
        errors.append("Accolades CSS non équilibrées")

    for block in re.findall(r"\{([^{}]*)\}", text, flags=re.DOTALL):
        declarations = [line.strip() for line in block.splitlines() if line.strip()]

        for line in declarations:
            if line.startswith(("/*", "*", "@")):
                continue
            if ":" in line and not line.endswith(";"):
                errors.append(f"Ligne CSS sans point-virgule : {line}")

    return {
        "valid": not errors,
        "errors": errors,
    }


def validate_js(content):
    """
    Vérifie la syntaxe JS basique.
    Retourne {"valid": True/False, "errors": [...]}
    """
    text = str(content or "")
    errors = []

    if text.count("(") != text.count(")"):
        errors.append("Parenthèses JS non équilibrées")

    if text.count("{") != text.count("}"):
        errors.append("Accolades JS non équilibrées")

    return {
        "valid": not errors,
        "errors": errors,
    }


def validate_file(path):
    """
    Détecte le type et valide.
    Retourne {"valid": True/False, "errors": [...], "type": "html|css|js"}
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".html":
        file_type = "html"
    elif suffix == ".css":
        file_type = "css"
    elif suffix == ".js":
        file_type = "js"
    else:
        return {
            "valid": False,
            "errors": [f"Type de fichier non supporté : {suffix}"],
            "type": "",
        }

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as error:
        return {
            "valid": False,
            "errors": [str(error)],
            "type": file_type,
        }

    if file_type == "html":
        result = validate_html(content)
    elif file_type == "css":
        result = validate_css(content)
    else:
        result = validate_js(content)

    result["type"] = file_type
    return result


def quality_score(path):
    """
    Calcule un score qualité 0-100.

    100 = excellent
    80+ = bon
    50-79 = moyen
    <50 = faible
    """

    try:
        file_path = Path(path)

        if not file_path.exists():
            return {
                "score": 0,
                "category": "faible",
                "errors": ["Fichier introuvable"],
                "details": {}
            }

        content = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        validation = validate_file(path)

        score = 100
        details = {}

        lower = content.lower()

        # =========================
        # MALUS
        # =========================

        if "<!doctype html>" not in lower:
            score -= 15
            details["doctype"] = False

        if "<html" not in lower:
            score -= 10
            details["html"] = False

        if "<body" not in lower:
            score -= 10
            details["body"] = False

        if "<head" not in lower:
            score -= 5
            details["head"] = False

        if "<title" not in lower:
            score -= 5
            details["title"] = False

        if "<style" not in lower and 'rel="stylesheet"' not in lower:
            score -= 5
            details["css"] = False

        text_only = re.sub(r"<[^>]+>", "", content).strip()

        if len(text_only) < 50:
            score -= 20
            details["content_size"] = "very_small"

        elif len(text_only) < 200:
            score -= 10
            details["content_size"] = "small"

        errors = validation.get("errors", [])

        for error in errors:

            score -= 5

            if "Balise mal formée" in error:
                score -= 10

            if "Attribut sans guillemets" in error:
                score -= 3

        # =========================
        # BONUS
        # =========================

        if "<style" in lower or 'rel="stylesheet"' in lower:
            score += 5

        if "<script" in lower:
            score += 5

        if len(content) > 500:
            score += 10

        if "width=device-width" in lower:
            score += 5

        # =========================
        # LIMITES
        # =========================

        score = max(0, min(100, score))

        # =========================
        # CATÉGORIE
        # =========================

        if score >= 90:
            category = "excellent"

        elif score >= 70:
            category = "bon"

        elif score >= 50:
            category = "moyen"

        else:
            category = "faible"

        return {
            "score": score,
            "category": category,
            "errors": errors,
            "details": details
        }

    except Exception as e:
        return {
            "score": 0,
            "category": "faible",
            "errors": [str(e)],
            "details": {}
        }


def fitness_score(path):
    """
    Score multi-critères
    0-100 combinant :
    - validation
    - richesse contenu
    - responsive
    - navigation
    - accessibilité
    """

    import re
    from pathlib import Path

    technical_result = quality_score(path)

    technical_score = technical_result.get(
        "score",
        0
    )

    file_path = Path(path)

    if not file_path.exists():

        return {
            "fitness": 0,
            "technical": 0,
            "content": 0,
            "sections": 0,
            "responsive": 0,
            "navigation": 0,
            "accessibility": 0,
            "errors": ["Fichier introuvable"]
        }

    content = file_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    lower = content.lower()

    text_only = re.sub(
        r"<[^>]+>",
        " ",
        content
    )

    words = re.findall(
        r"\b\w+\b",
        text_only
    )

    word_count = len(words)

    content_score = 0

    if word_count >= 1000:
        content_score = 20

    elif word_count >= 500:
        content_score = 15

    elif word_count >= 200:
        content_score = 10

    elif word_count >= 50:
        content_score = 5

    sections_found = 0

    section_keywords = [
        "hero",
        "features",
        "pricing",
        "testimonial",
        "cta",
        "footer"
    ]

    for keyword in section_keywords:

        if keyword in lower:
            sections_found += 1

    sections_score = min(
        15,
        sections_found * 2.5
    )

    responsive_score = 0

    if "@media" in lower:
        responsive_score += 8

    if "viewport" in lower:
        responsive_score += 4

    if (
        "display:flex" in lower
        or "display: flex" in lower
        or "display:grid" in lower
        or "display: grid" in lower
    ):
        responsive_score += 3

    responsive_score = min(
        15,
        responsive_score
    )

    navigation_score = 0

    nav_links = re.findall(
        r"<a\s+[^>]*href=",
        lower
    )

    if len(nav_links) > 2:
        navigation_score += 5

    if "<footer" in lower:
        navigation_score += 3

    internal_links = [
        link for link in nav_links
        if (
            ".html"
            in link
            or "#"
            in link
        )
    ]

    if internal_links:
        navigation_score += 2

    navigation_score = min(
        10,
        navigation_score
    )

    accessibility_score = 0

    images = re.findall(
        r"<img[^>]*>",
        lower
    )

    if images:

        with_alt = [
            img for img in images
            if "alt=" in img
        ]

        if len(with_alt) == len(images):
            accessibility_score += 4

    if "aria-" in lower:
        accessibility_score += 3

    if "lang=" in lower:
        accessibility_score += 3

    accessibility_score = min(
        10,
        accessibility_score
    )

    fitness = (
        (technical_score * 0.30)
        + content_score
        + sections_score
        + responsive_score
        + navigation_score
        + accessibility_score
    )

    fitness = round(
        min(100, fitness),
        2
    )

    return {
        "fitness": fitness,
        "technical": technical_score,
        "content": content_score,
        "sections": sections_score,
        "responsive": responsive_score,
        "navigation": navigation_score,
        "accessibility": accessibility_score,
        "errors": technical_result.get(
            "errors",
            []
        )
    }


def _find_unclosed_html_tags(content):
    errors = []
    stack = []
    tags = re.findall(r"<\s*(/)?\s*([A-Za-z][A-Za-z0-9-]*)(?:\s[^<>]*)?>", content)

    for closing, tag_name in tags:
        tag = tag_name.lower()

        if tag.startswith("!"):
            continue

        if tag in VOID_TAGS:
            continue

        if not closing:
            stack.append(tag)
            continue

        if not stack:
            errors.append(f"Balise fermante sans ouverture : </{tag}>")
            continue

        if stack[-1] == tag:
            stack.pop()
            continue

        if tag in stack:
            while stack and stack[-1] != tag:
                missing = stack.pop()
                errors.append(f"Balise non fermée : <{missing}>")
            if stack:
                stack.pop()
            continue

        errors.append(f"Balise fermante inattendue : </{tag}>")

    for tag in reversed(stack):
        errors.append(f"Balise non fermée : <{tag}>")

    return errors
