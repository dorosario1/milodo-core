from importlib import import_module
from pathlib import Path

from logger import log_info, log_error, log_warn, log_debug


SKILL_NAMES = {
    "site_generator",
    "test_generator",
    "doc_generator",
    "git_manager",
    "csv_analyzer",
}


def execute_actions(actions, output_dir):
    total = len(actions) if isinstance(actions, list) else 0
    results = []
    completed = 0
    failed = 0

    if not isinstance(actions, list):
        log_error("actions doit etre une liste")
        return {
            "success": False,
            "total": 0,
            "completed": 0,
            "failed": 1,
            "results": [{
                "success": False,
                "action": None,
                "error": "actions doit etre une liste",
            }],
            "output_dir": str(output_dir),
        }

    for item in actions:
        action = None
        params = {}

        try:
            if not isinstance(item, dict):
                raise ValueError("Action invalide: dictionnaire attendu")

            action = item.get("action")
            params = item.get("params") or {}

            if not isinstance(params, dict):
                raise ValueError("params doit etre un dictionnaire")

            log_debug(f"Params : {params}")
            result = _execute_one(action, params, output_dir)

            if _is_success(result):
                completed += 1
                log_info(f"Action exécutée : {action}")
            else:
                failed += 1

            results.append({
                "success": _is_success(result),
                "action": action,
                "result": result,
                "error": _extract_error(result),
            })
        except Exception as error:
            failed += 1
            log_error(f"Erreur action {action} : {error}")
            results.append({
                "success": False,
                "action": action,
                "result": None,
                "error": str(error),
            })

    # Sauvegarder dans state_recall
    try:
        from state_recall import remember_last_project

        remember_last_project({
            "name": output_dir.name if output_dir else "projet",
            "output_dir": str(output_dir),
            "actions_count": completed,
            "date": __import__('datetime').datetime.now().isoformat()
        })

        log_info("Projet mémorisé dans state_recall")

    except Exception as e:
        log_warn(f"Impossible de mémoriser le projet : {e}")

    return {
        "success": failed == 0,
        "total": total,
        "completed": completed,
        "failed": failed,
        "results": results,
        "output_dir": str(output_dir),
    }


def _execute_one(action, params, output_dir):
    action_name = str(action or "").strip()

    if action_name in {"create_landing", "create_site", "generate_site"}:
        skill = _load_module("site_generator")
        call_params = _with_output_dir(params, output_dir)
        return skill.run(action="generate", **call_params)

    if action_name == "create_page":
        return _create_page(params, output_dir)

    if action_name == "generate_code":
        coding_agent = _load_module("coding_agent")
        prompt = params.get("prompt") or params.get("content") or params.get("instruction") or ""
        return coding_agent.generate_code(prompt)

    if action_name == "create_file":
        return _create_file(params, output_dir)

    if action_name == "run_tests":
        skill = _load_module("test_generator")
        return skill.run(action="analyze_file", **params)

    if action_name == "generate_docs":
        skill = _load_module("doc_generator")
        return skill.run(action="readme", **_with_doc_defaults(params, output_dir))

    if action_name == "git_init":
        skill = _load_module("git_manager")
        return skill.run(action="init", **_with_cwd(params, output_dir))

    if action_name == "git_commit":
        skill = _load_module("git_manager")
        return skill.run(action="commit", **_with_cwd(params, output_dir))

    if action_name == "csv_analyze":
        skill = _load_module("csv_analyzer")
        return skill.run(action="analyze", **params)

    log_warn(f"Action inconnue : {action}")
    return {
        "success": False,
        "error": f"Action inconnue : {action}",
    }


def _create_page(params, output_dir):
    name = params.get("name") or "page"
    path = params.get("path")

    if not path:
        path = Path(output_dir) / f"{_safe_file_stem(name)}.html"
    else:
        path = _resolve_output_path(path, output_dir)

    project_name = params.get("project_name") or "Le Gourmet"
    prompt = f"""Génère une page HTML5 complète et responsive pour un site de restaurant appelé "{project_name}".

Page : {name}
Contexte : {params.get('description', '')}

EXIGENCES :
- Design sombre élégant (fond #1a1a2e)
- Contenu réaliste et détaillé (pas de placeholder)
- Si c'est une page menu : liste de plats avec noms, descriptions, prix
- Si c'est une page contact : formulaire, adresse, téléphone, horaires
- Si c'est une page accueil : hero, présentation, plats vedettes, témoignages
- Header avec navigation, footer avec copyright
- CSS intégré dans <style> ou lié à style.css
- Au moins 300 mots de contenu réel
- En français
"""
    coding_agent = _load_module("coding_agent")
    file_tools = _load_module("file_tools")

    html = coding_agent.generate_code(prompt)

    if not html or len(str(html)) <= 50:
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{name}</title>
</head>
<body>
    <h1>{name}</h1>
</body>
</html>
"""

    file_tools.write_file(path, str(html))
    return {
        "success": True,
        "path": str(path),
    }


def _create_file(params, output_dir):
    path = params.get("path") or params.get("name")

    if not path:
        raise ValueError("create_file requiert path ou name")

    file_path = _resolve_output_path(path, output_dir)

    if "content" not in params:
        raise ValueError("create_file requiert content")

    file_tools = _load_module("file_tools")
    file_tools.write_file(file_path, str(params.get("content", "")))
    return {
        "success": True,
        "path": str(file_path),
    }


def _load_module(name):
    if name in SKILL_NAMES:
        module = _load_skill_module(name)
        if module is not None:
            return module

    return import_module(name)


def _load_skill_module(name):
    try:
        skill_loader = import_module("skill_loader")
        skill_path = Path(__file__).resolve().parent / "skills" / f"{name}.py"

        if hasattr(skill_loader, "load_skill"):
            loaded = skill_loader.load_skill(skill_path)
            if loaded.get("success") and loaded.get("module") is not None:
                return loaded["module"]

        if hasattr(skill_loader, "scan_skills") and hasattr(skill_loader, "load_skill"):
            for skill_path in skill_loader.scan_skills():
                if Path(skill_path).stem == name:
                    loaded = skill_loader.load_skill(skill_path)
                    if loaded.get("success") and loaded.get("module") is not None:
                        return loaded["module"]
    except Exception as error:
        log_warn(f"Chargement skill_loader impossible pour {name} : {error}")

    try:
        return import_module(f"skills.{name}")
    except Exception as error:
        log_warn(f"Import direct skill impossible pour {name} : {error}")
        return None


def _with_output_dir(params, output_dir):
    call_params = dict(params)
    call_params.setdefault("output_dir", str(output_dir))
    return call_params


def _with_cwd(params, output_dir):
    call_params = dict(params)
    call_params.setdefault("cwd", str(output_dir))
    return call_params


def _with_doc_defaults(params, output_dir):
    call_params = dict(params)
    call_params.setdefault("project_dir", str(output_dir))
    call_params.setdefault("project_name", Path(output_dir).name or "milodo-project")
    return call_params


def _resolve_output_path(path, output_dir):
    file_path = Path(path)

    if file_path.is_absolute():
        return file_path

    return Path(output_dir) / file_path


def _is_success(result):
    if isinstance(result, dict) and "success" in result:
        return bool(result.get("success"))

    return result is not None


def _extract_error(result):
    if isinstance(result, dict):
        return result.get("error") or None

    return None


def _safe_file_stem(value):
    text = str(value or "page").strip().lower()
    chars = []

    for char in text:
        if char.isalnum():
            chars.append(char)
        elif char in (" ", "-", "_"):
            chars.append("_")

    stem = "".join(chars).strip("_")

    while "__" in stem:
        stem = stem.replace("__", "_")

    return stem or "page"
