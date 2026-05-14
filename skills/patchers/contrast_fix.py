PATCHER_NAME = "contrast"
PATCHER_VERSION = "1.0.0"

import re


def apply_patch(content, issue):
    return re.sub(r'color:\s*(#000|#000000|black)', 'color: #ffffff', content, count=1, flags=re.IGNORECASE)


def validate(content):
    return "#ffffff" in content.lower() and len(content) > 10


def describe(issue):
    return f"Remplacer couleur sombre par clair dans {issue['file']}"
