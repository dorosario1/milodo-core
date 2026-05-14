PATCHER_NAME = "localization_spacing"
PATCHER_VERSION = "1.0.0"


def apply_patch(content, issue):
    if ".localization-form" in content:
        if "margin-right" not in content:
            content += "\n.localization-form,\n.language-selector {\n    margin-right: 12px;\n}\n"
        if "padding-inline" not in content:
            content += "\n.localization-form__select {\n    padding-inline: 12px 28px;\n    border-radius: 12px;\n}\n"
    return content


def validate(content):
    return "margin-right" in content and len(content) > 10


def describe(issue):
    return f"Ajouter spacing au selecteur de localisation dans {issue['file']}"
