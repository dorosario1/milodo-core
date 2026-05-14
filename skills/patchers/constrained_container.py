PATCHER_NAME = "constrained_container"
PATCHER_VERSION = "1.0.0"


def apply_patch(content, issue):
    # Ne s'applique qu'aux fichiers JSON contenant section_width
    if "section_width" not in content:
        return content

    if '"section_width": "page-width"' in content:
        return content.replace('"section_width": "page-width"', '"section_width": "full-width"')
    return content


def validate(content):
    return "full-width" in content and len(content) > 10


def describe(issue):
    return f"Remplacer page-width par full-width dans {issue['file']}"
