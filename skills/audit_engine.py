import json
from html.parser import HTMLParser


class _AuditHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_text = ""
        self._in_title = False
        self.meta = []
        self.h1_texts = []
        self._in_h1 = False
        self.images = []
        self.links = []
        self._current_link = None
        self.canonical_links = []
        self.json_ld_blocks = []
        self._in_json_ld = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._in_title = True
        elif tag_lower == "meta":
            self.meta.append(attrs_dict)
        elif tag_lower == "h1":
            self._in_h1 = True
            self.h1_texts.append("")
        elif tag_lower == "img":
            self.images.append(attrs_dict)
        elif tag_lower == "a":
            self._current_link = {
                "attrs": attrs_dict,
                "text": "",
            }
            self.links.append(self._current_link)
        elif tag_lower == "link":
            rel = (attrs_dict.get("rel") or "").lower()
            if rel == "canonical":
                self.canonical_links.append(attrs_dict)
        elif tag_lower == "script":
            script_type = (attrs_dict.get("type") or "").lower()
            if script_type == "application/ld+json":
                self._in_json_ld = True
                self.json_ld_blocks.append("")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._in_title = False
        elif tag_lower == "h1":
            self._in_h1 = False
        elif tag_lower == "a":
            self._current_link = None
        elif tag_lower == "script":
            self._in_json_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title_text += data

        if self._in_h1 and self.h1_texts:
            self.h1_texts[-1] += data

        if self._current_link is not None:
            self._current_link["text"] += data

        if self._in_json_ld and self.json_ld_blocks:
            self.json_ld_blocks[-1] += data


def _issue(issue_type, severity, description):
    return {
        "type": issue_type,
        "severity": severity,
        "description": description,
    }


def _check_title(parser):
    text = parser.title_text.strip()
    length = len(text)
    issues = []

    if not text:
        issues.append(_issue("missing_title", "high", "Balise title absente."))
        score = 0.0
    elif 30 <= length <= 65:
        score = 1.0
    else:
        issues.append(
            _issue(
                "title_length",
                "medium",
                f"Longueur title non optimale ({length} caractères).",
            )
        )
        score = 0.5

    return {
        "score": score,
        "present": bool(text),
        "length": length,
        "issues": issues,
    }


def _check_meta_description(parser):
    content = ""
    for meta in parser.meta:
        if (meta.get("name") or "").lower() == "description":
            content = (meta.get("content") or "").strip()
            break

    length = len(content)
    issues = []

    if not content:
        issues.append(
            _issue(
                "missing_meta_description",
                "high",
                "Meta description absente.",
            )
        )
        score = 0.0
    elif 120 <= length <= 160:
        score = 1.0
    else:
        issues.append(
            _issue(
                "meta_description_length",
                "medium",
                f"Longueur meta description non optimale ({length} caractères).",
            )
        )
        score = 0.5

    return {
        "score": score,
        "present": bool(content),
        "length": length,
        "issues": issues,
    }


def _check_h1(parser):
    h1_texts = [text.strip() for text in parser.h1_texts if text.strip()]
    count = len(h1_texts)
    issues = []

    if count == 0:
        issues.append(_issue("missing_h1", "high", "Aucun H1 présent."))
        score = 0.0
    elif count == 1:
        score = 1.0
    else:
        issues.append(_issue("multiple_h1", "medium", f"{count} H1 détectés."))
        score = 0.5

    return {
        "score": score,
        "count": count,
        "issues": issues,
    }


def _check_images_alt(parser):
    total = len(parser.images)
    with_alt = len([
        image for image in parser.images
        if (image.get("alt") or "").strip()
    ])
    ratio = 1.0 if total == 0 else with_alt / total
    issues = []

    if ratio < 1.0:
        issues.append(
            _issue(
                "images_missing_alt",
                "medium",
                f"{total - with_alt}/{total} images sans alt non vide.",
            )
        )

    return {
        "score": round(ratio, 4),
        "total": total,
        "with_alt": with_alt,
        "ratio": round(ratio, 4),
        "issues": issues,
    }


def _check_links_descriptive(parser):
    weak_texts = {
        "ici",
        "click here",
        "cliquez ici",
        "read more",
        "en savoir plus",
        "voir plus",
        "more",
    }
    texts = [
        link["text"].strip().lower()
        for link in parser.links
        if link["text"].strip()
    ]
    weak_count = len([text for text in texts if text in weak_texts])
    total = len(texts)
    issues = []

    if weak_count:
        issues.append(
            _issue(
                "weak_link_text",
                "low",
                f"{weak_count} lien(s) non descriptif(s).",
            )
        )

    if total == 0:
        score = 1.0
    else:
        score = max(0.0, 1.0 - (weak_count / total))

    return {
        "score": round(score, 4),
        "total": total,
        "weak_count": weak_count,
        "issues": issues,
    }


def _check_canonical(parser):
    present = any((link.get("href") or "").strip() for link in parser.canonical_links)
    issues = []

    if not present:
        issues.append(_issue("missing_canonical", "medium", "Lien canonical absent."))

    return {
        "score": 1.0 if present else 0.0,
        "present": present,
        "issues": issues,
    }


def _check_open_graph(parser):
    properties = {
        meta.get("property"): meta.get("content")
        for meta in parser.meta
        if meta.get("property")
    }
    required = ["og:title", "og:description", "og:url"]
    missing = [
        prop for prop in required
        if not (properties.get(prop) or "").strip()
    ]
    issues = []

    if missing:
        issues.append(
            _issue(
                "missing_open_graph",
                "medium",
                f"Open Graph incomplet : {', '.join(missing)}.",
            )
        )

    score = (len(required) - len(missing)) / len(required)
    return {
        "score": round(score, 4),
        "missing": missing,
        "issues": issues,
    }


def _check_structured_data(parser):
    valid_blocks = 0
    issues = []

    for block in parser.json_ld_blocks:
        try:
            json.loads(block)
            valid_blocks += 1
        except json.JSONDecodeError:
            continue

    if valid_blocks == 0:
        issues.append(
            _issue(
                "missing_structured_data",
                "medium",
                "Aucune donnée structurée JSON-LD valide.",
            )
        )

    return {
        "score": 1.0 if valid_blocks else 0.0,
        "valid_blocks": valid_blocks,
        "issues": issues,
    }


def audit_html(html: str) -> dict:
    parser = _AuditHTMLParser()
    parser.feed(html or "")

    checks = {
        "title": _check_title(parser),
        "meta_description": _check_meta_description(parser),
        "h1": _check_h1(parser),
        "images_alt": _check_images_alt(parser),
        "links_descriptive": _check_links_descriptive(parser),
        "canonical": _check_canonical(parser),
        "open_graph": _check_open_graph(parser),
        "structured_data": _check_structured_data(parser),
    }

    issues = [
        issue
        for check in checks.values()
        for issue in check["issues"]
    ]
    score = round(
        (sum(check["score"] for check in checks.values()) / len(checks)) * 100,
        2,
    )

    return {
        "score": score,
        "checks": checks,
        "issues": issues,
    }
