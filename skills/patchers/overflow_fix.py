PATCHER_NAME = "overflow_risk"
PATCHER_VERSION = "1.0.0"


def apply_patch(content, issue):
    if "overflow-x" not in content:
        return content.replace('class="', 'style="overflow-x: hidden; max-width: 100vw;" class="', 1)
    return content


def validate(content):
    return "overflow-x" in content and len(content) > 10


def describe(issue):
    return f"Ajouter overflow-x: hidden dans {issue['file']}"
