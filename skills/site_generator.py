SKILL_NAME = "site_generator"
SKILL_DESCRIPTION = "Génère un site web multi-pages HTML/CSS/JS vanilla avec structure propre"
SKILL_VERSION = "1.0.0"

import webbrowser
from pathlib import Path


SUPPORTED_TYPES = {"landing", "portfolio", "vitrine", "blank"}


def run(action, **kwargs):
    try:
        action_name = str(action or "").strip().lower()

        if action_name == "generate":
            return _generate_site(
                kwargs.get("name"),
                kwargs.get("type"),
                kwargs.get("pages"),
                kwargs.get("output_dir"),
            )

        if action_name == "preview":
            return _preview(kwargs.get("output_dir"))

        return _error(f"Action inconnue: {action}")
    except Exception as error:
        return _error(str(error))


def _generate_site(name, site_type, pages, output_dir):
    if not name:
        return _error("name est requis")

    if not output_dir:
        return _error("output_dir est requis")

    site_type = str(site_type or "blank").strip().lower()

    if site_type not in SUPPORTED_TYPES:
        return _error(f"type non supporte: {site_type}")

    page_names = _normalize_pages(pages)
    site_name = _safe_name(name)
    root_dir = Path(output_dir) / site_name
    css_dir = root_dir / "css"
    js_dir = root_dir / "js"
    pages_dir = root_dir / "pages"

    css_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    files_created = []
    index_path = root_dir / "index.html"
    css_path = css_dir / "style.css"
    js_path = js_dir / "script.js"

    _write(index_path, _html_page(site_name, site_type, "Accueil", page_names, True))
    _write(css_path, _css_content())
    _write(js_path, _js_content())
    files_created.extend([str(index_path), str(css_path), str(js_path)])

    created_pages = []

    for page in page_names:
        page_path = pages_dir / f"{_safe_name(page)}.html"
        _write(page_path, _html_page(site_name, site_type, page.title(), page_names, False))
        created_pages.append(str(page_path))
        files_created.append(str(page_path))

    return {
        "success": True,
        "output_dir": str(root_dir),
        "pages": created_pages,
        "files_created": files_created,
    }


def _preview(output_dir):
    if not output_dir:
        return _error("output_dir est requis")

    index_path = Path(output_dir) / "index.html"

    if not index_path.exists():
        return _error(f"index.html introuvable: {index_path}")

    webbrowser.open(index_path.resolve().as_uri())

    return {
        "success": True,
        "output_dir": str(Path(output_dir)),
        "pages": [],
        "files_created": [str(index_path)],
    }


def _html_page(site_name, site_type, title, pages, is_index):
    nav_prefix = "" if is_index else "../"
    home_href = f"{nav_prefix}index.html"
    links = [f'<a href="{home_href}">Accueil</a>']

    for page in pages:
        href = f"{nav_prefix}pages/{_safe_name(page)}.html" if is_index else f"{_safe_name(page)}.html"
        links.append(f'<a href="{href}">{page.title()}</a>')

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - {site_name}</title>
  <link rel="stylesheet" href="{nav_prefix}css/style.css">
</head>
<body>
  <header class="site-header">
    <nav class="container nav">
      <a class="brand" href="{home_href}">{site_name}</a>
      <div class="nav-links">
        {"".join(links)}
      </div>
    </nav>
  </header>

  <main class="container main-content">
    <section class="hero">
      <p class="eyebrow">{site_type}</p>
      <h1>{title}</h1>
      <p>Site généré par MILODO avec HTML, CSS et JavaScript vanilla.</p>
    </section>

    <section class="content-section">
      <h2>Contenu principal</h2>
      <p>Personnalisez cette page selon votre objectif.</p>
    </section>
  </main>

  <footer class="site-footer">
    <div class="container">© {site_name}</div>
  </footer>

  <script src="{nav_prefix}js/script.js"></script>
</body>
</html>
"""


def _css_content():
    return """* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  min-height: 100vh;
  font-family: Arial, sans-serif;
  background: #1a1a2e;
  color: #f4f4f5;
  line-height: 1.6;
}

a {
  color: inherit;
  text-decoration: none;
}

.container {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
}

.site-header {
  border-bottom: 1px solid #2f3350;
  background: #121225;
}

.nav {
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.brand {
  font-weight: 700;
}

.nav-links {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.nav-links a {
  color: #d4d4d8;
}

.nav-links a.active,
.nav-links a:hover {
  color: #7dd3fc;
}

.main-content {
  padding: 56px 0;
}

.hero {
  max-width: 760px;
  padding: 40px 0;
}

.eyebrow {
  color: #7dd3fc;
  text-transform: uppercase;
  font-size: 13px;
  margin-bottom: 12px;
}

h1 {
  font-size: 42px;
  margin-bottom: 16px;
}

.content-section {
  padding: 28px;
  border: 1px solid #2f3350;
  background: #20203a;
  border-radius: 8px;
}

.site-footer {
  border-top: 1px solid #2f3350;
  padding: 24px 0;
  color: #a1a1aa;
}

@media (max-width: 720px) {
  .nav {
    align-items: flex-start;
    flex-direction: column;
    padding: 16px 0;
  }

  h1 {
    font-size: 32px;
  }

  .main-content {
    padding: 32px 0;
  }
}
"""


def _js_content():
    return """console.log("MILODO generated");

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth" });
    }
  });
});

const currentPath = window.location.pathname.split("/").pop() || "index.html";
document.querySelectorAll(".nav-links a").forEach((link) => {
  const linkPath = link.getAttribute("href").split("/").pop();
  if (linkPath === currentPath) {
    link.classList.add("active");
  }
});
"""


def _normalize_pages(pages):
    if not pages:
        return ["about", "contact"]

    if isinstance(pages, str):
        return [_safe_name(item) for item in pages.split(",") if item.strip()]

    return [_safe_name(item) for item in pages if str(item).strip()]


def _safe_name(value):
    text = str(value).strip().lower()
    clean = []

    for char in text:
        if char.isalnum():
            clean.append(char)
        elif char in (" ", "-", "_"):
            clean.append("_")

    result = "".join(clean).strip("_")

    while "__" in result:
        result = result.replace("__", "_")

    return result or "site"


def _write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def _error(message):
    return {
        "success": False,
        "output_dir": "",
        "pages": [],
        "files_created": [],
        "error": message,
    }
