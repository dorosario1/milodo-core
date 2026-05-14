import importlib


PATCHERS = {
    "constrained_container": "skills.patchers.constrained_container",
    "overflow_risk": "skills.patchers.overflow_fix",
    "contrast": "skills.patchers.contrast_fix",
    "cta_weak": "skills.patchers.cta_fix",
    "localization_spacing": "skills.patchers.localization_spacing",
}


def get_patcher(issue_type):
    module_path = PATCHERS.get(issue_type)
    if module_path:
        return importlib.import_module(module_path)
    return None
