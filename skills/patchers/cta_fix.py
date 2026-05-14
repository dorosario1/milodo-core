PATCHER_NAME = "cta_weak"
PATCHER_VERSION = "1.0.0"


def apply_patch(content, issue):
    if "button" in content.lower():
        return content.replace('class="button', 'style="font-size: 1rem; padding: 12px 24px;" class="button', 1)
    return content


def validate(content):
    return "font-size" in content and len(content) > 10


def describe(issue):
    return f"Ajouter font-size et padding au bouton dans {issue['file']}"
