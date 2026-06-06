import json
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath


class _PatchParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.h1_text = ""
        self.meta_description = ""
        self.images = []
        self.links = []
        self.canonical = ""
        self.og_tags = {}
        self.has_jsonld = False
        self._in_title = False
        self._in_h1 = False
        self._current_link = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag = tag.lower()

        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "meta":
            name = (attrs_dict.get("name") or "").lower()
            prop = (attrs_dict.get("property") or "").lower()
            if name == "description":
                self.meta_description = attrs_dict.get("content", "")
            if prop.startswith("og:"):
                self.og_tags[prop] = attrs_dict.get("content", "")
        elif tag == "img":
            self.images.append(attrs_dict)
        elif tag == "a":
            self._current_link = {"attrs": attrs_dict, "text": ""}
            self.links.append(self._current_link)
        elif tag == "link":
            if (attrs_dict.get("rel") or "").lower() == "canonical":
                self.canonical = attrs_dict.get("href", "")
        elif tag == "script":
            if (attrs_dict.get("type") or "").lower() == "application/ld+json":
                self.has_jsonld = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "a":
            self._current_link = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h1:
            self.h1_text += data
        if self._current_link is not None:
            self._current_link["text"] += data


def _insert_before_head_close(html, snippet):
    if re.search(r"</head>", html, re.IGNORECASE):
        return re.sub(
            r"</head>",
            f"{snippet}\n</head>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    return snippet + "\n" + html


def _truncate_clean(text, max_length):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0].strip()
    return truncated or text[:max_length].strip()


def _fix_title(html, parser):
    current_title = parser.title.strip()
    if current_title and len(current_title) >= 30:
        return html

    base = parser.h1_text.strip() or current_title or "Notre site"
    title = _truncate_clean(f"{base} | Découvrez notre collection", 65)

    if re.search(r"<title>.*?</title>", html, re.IGNORECASE | re.DOTALL):
        return re.sub(
            r"<title>.*?</title>",
            f"<title>{title}</title>",
            html,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return _insert_before_head_close(html, f"    <title>{title}</title>")


def _body_text(html):
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.IGNORECASE | re.DOTALL)
    body = body_match.group(1) if body_match else html
    text = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", text).strip()


def _fix_meta_description(html, parser):
    current = parser.meta_description.strip()
    if current and len(current) >= 120:
        return html

    content = _truncate_clean(_body_text(html), 160) or "Découvrez notre site."
    tag = f'    <meta name="description" content="{content}">'

    if re.search(
        r'<meta[^>]+name=["\']description["\'][^>]*>',
        html,
        re.IGNORECASE,
    ):
        return re.sub(
            r'<meta[^>]+name=["\']description["\'][^>]*>',
            tag.strip(),
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    return _insert_before_head_close(html, tag)


def _alt_from_src(src):
    filename = PurePosixPath((src or "").split("?", 1)[0]).stem
    cleaned = filename.replace("-", " ").replace("_", " ").strip()
    return cleaned.title() if cleaned else "Image descriptive"


def _fix_images_alt(html, parser):
    def replace_img(match):
        tag = match.group(0)
        src_match = re.search(r'\bsrc=["\']([^"\']*)["\']', tag, re.IGNORECASE)
        src = src_match.group(1) if src_match else ""
        replacement_alt = _alt_from_src(src)

        if re.search(r'\balt=["\']\s*["\']', tag, re.IGNORECASE):
            return re.sub(
                r'\balt=["\']\s*["\']',
                f'alt="{replacement_alt}"',
                tag,
                count=1,
                flags=re.IGNORECASE,
            )

        if not re.search(r"\balt=", tag, re.IGNORECASE):
            return tag[:-1] + f' alt="{replacement_alt}">'

        return tag

    return re.sub(r"<img\b[^>]*>", replace_img, html, flags=re.IGNORECASE)


def _fix_links(html, parser):
    replacements = {
        "cliquez ici": "Découvrir",
        "ici": "Détails",
        "click here": "Découvrir",
        "here": "Détails",
        "en savoir plus": "En savoir plus",
        "read more": "En savoir plus",
    }

    def replace_link(match):
        opening = match.group(1)
        text = match.group(2)
        closing = match.group(3)
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        replacement = replacements.get(normalized)
        return f"{opening}{replacement or text}{closing}"

    return re.sub(
        r"(<a\b[^>]*>)(.*?)(</a>)",
        replace_link,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _fix_canonical(html, parser):
    if parser.canonical.strip():
        return html
    return _insert_before_head_close(
        html,
        '    <link rel="canonical" href="https://www.example.com/">',
    )


def _fix_og_tags(html, parser):
    reparsed = _PatchParser()
    reparsed.feed(html)
    title = reparsed.title.strip() or "Notre site"
    description = reparsed.meta_description.strip() or "Découvrez notre site."
    canonical = reparsed.canonical.strip() or "https://www.example.com/"

    additions = []
    if not reparsed.og_tags.get("og:title"):
        additions.append(f'    <meta property="og:title" content="{title}">')
    if not reparsed.og_tags.get("og:description"):
        additions.append(f'    <meta property="og:description" content="{description}">')
    if not reparsed.og_tags.get("og:url"):
        additions.append(f'    <meta property="og:url" content="{canonical}">')

    if not additions:
        return html

    return _insert_before_head_close(html, "\n".join(additions))


def _fix_jsonld(html, parser):
    reparsed = _PatchParser()
    reparsed.feed(html)
    if reparsed.has_jsonld:
        return html

    payload = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": reparsed.h1_text.strip() or reparsed.title.strip() or "Produit",
    }
    snippet = (
        '    <script type="application/ld+json">\n'
        f"    {json.dumps(payload, ensure_ascii=False)}\n"
        "    </script>"
    )
    return _insert_before_head_close(html, snippet)


def generate_patched_html(original_html: str, audit_before: dict) -> str:
    parser = _PatchParser()
    parser.feed(original_html or "")

    html = original_html
    html = _fix_title(html, parser)
    html = _fix_meta_description(html, parser)
    html = _fix_images_alt(html, parser)
    html = _fix_links(html, parser)
    html = _fix_canonical(html, parser)
    html = _fix_og_tags(html, parser)
    html = _fix_jsonld(html, parser)
    return html
