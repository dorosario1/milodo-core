from importlib import import_module
from pathlib import Path
import re
import unicodedata

from coding_agent import auto_fix_loop
from logger import log_info, log_error, log_warn, log_debug
from validate_file import quality_score


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
    files_created = []
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
            "files_created": files_created,
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

            if (
                action == "generate_code"
                and isinstance(result, str)
                and result.strip()
            ):
                prompt_text = str(
                    params.get("prompt")
                    or params.get("content")
                    or params.get("instruction")
                    or ""
                )
                prompt_and_result = f"{prompt_text}\n{result}".lower()
                file_params = {
                    "content": result,
                    "path": params.get("path"),
                    "name": params.get("name"),
                }

                if not file_params.get("path") and not file_params.get("name"):
                    if (
                        "<!doctype html" in prompt_and_result
                        or "<html" in prompt_and_result
                        or " html" in prompt_and_result
                    ):
                        file_params["name"] = "index.html"
                    elif (
                        "python" in prompt_and_result
                        or "def " in result
                        or "print(" in result
                        or "import " in result
                    ):
                        file_params["name"] = "generated.py"
                    elif (
                        "readme" in prompt_and_result
                        or "markdown" in prompt_and_result
                        or result.lstrip().startswith("#")
                    ):
                        file_params["name"] = "README.md"
                    elif (
                        "json" in prompt_and_result
                        or (
                            result.lstrip().startswith("{")
                            and result.rstrip().endswith("}")
                        )
                        or (
                            result.lstrip().startswith("[")
                            and result.rstrip().endswith("]")
                        )
                    ):
                        file_params["name"] = "generated.json"
                    elif (
                        "css" in prompt_and_result
                        or ("{" in result and "}" in result and ":" in result)
                    ):
                        file_params["name"] = "styles.css"
                    elif (
                        "javascript" in prompt_and_result
                        or " js" in prompt_and_result
                        or "console.log(" in result
                        or "function " in result
                        or "const " in result
                        or "let " in result
                    ):
                        file_params["name"] = "app.js"
                    else:
                        file_params["name"] = "generated.txt"

                result = _create_file(file_params, output_dir)

            if isinstance(result, dict):
                result_files_created = result.get("files_created")
                if isinstance(result_files_created, list):
                    files_created.extend(str(path) for path in result_files_created)
                elif result.get("path"):
                    files_created.append(str(result.get("path")))

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
        from datetime import datetime

        project_info = {
            "name": _memory_project_name(output_dir, actions),
            "output_dir": str(output_dir),
            "actions_count": completed,
            "actions": [
                r.get("action", "unknown")
                for r in results
            ],
            "date": datetime.now().isoformat(),
            "files_created": len([
                r for r in results
                if isinstance(r.get("result"), dict) and r.get("result", {}).get("path")
            ])
        }

        remember_last_project(project_info)

        log_info(
            f"Projet mémorisé : "
            f"{project_info['name']} "
            f"({completed} actions, "
            f"{project_info['files_created']} fichiers)"
        )

    except Exception as e:
        log_warn(f"Impossible de mémoriser le projet : {e}")

    return {
        "success": failed == 0,
        "total": total,
        "completed": completed,
        "failed": failed,
        "results": results,
        "files_created": files_created,
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
    fix_result = None
    score_result = {}

    try:

        fix_result = auto_fix_loop(path)

        score_result = quality_score(path)

        log_info(
            f"Qualité fichier : "
            f"{score_result['score']}/100 "
            f"({score_result['category']})"
        )

    except Exception as e:

        log_warn(
            f"Auto-fix impossible pour {path}: {e}"
        )

    return {
        "success": True,
        "path": str(path),
        "quality_score": score_result.get("score"),
        "quality_category": score_result.get("category"),
        "auto_fix": fix_result,
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
    fix_result = None
    score_result = {}

    if file_path.suffix.lower() in {".html", ".css", ".js"}:
        try:

            fix_result = auto_fix_loop(file_path)

            score_result = quality_score(file_path)

            log_info(
                f"Qualité fichier : "
                f"{score_result['score']}/100 "
                f"({score_result['category']})"
            )

        except Exception as e:

            log_warn(
                f"Auto-fix impossible pour {file_path}: {e}"
            )

    return {
        "success": True,
        "path": str(file_path),
        "quality_score": score_result.get("score"),
        "quality_category": score_result.get("category"),
        "auto_fix": fix_result,
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


def _memory_project_name(output_dir, actions):
    if not output_dir:
        return "projet"

    output_path = Path(output_dir)
    current_name = output_path.name or "projet"

    if current_name != "project":
        return current_name

    return _derive_project_name(actions)


def _derive_project_name(actions):
    action_names = set()
    context_parts = []

    for item in actions if isinstance(actions, list) else []:
        if not isinstance(item, dict):
            continue

        action = str(item.get("action") or "").strip()
        if action:
            action_names.add(action)
            context_parts.append(action)

        params = item.get("params") or {}
        if isinstance(params, dict):
            for key in ("prompt", "content", "instruction", "name", "type", "description", "path"):
                value = params.get(key)
                if value:
                    context_parts.append(str(value))

    context = _normalize_project_name(" ".join(context_parts))
    context_tokens = set(context.split("_"))

    if "create_landing" in action_names or "landing" in context:
        return "create_landing_page"

    if action_names.intersection({"create_site", "generate_site"}) or "site" in context:
        if "html" in context:
            return "create_site_html"
        return "create_site"

    if "python" in context_tokens or "py" in context_tokens:
        return "generated_python_script"

    if "script" in context:
        return "generated_script"

    return context or "generated_project"


def _normalize_project_name(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"\b(cree|creer|creez|créer|crée|créez)\b", "create", text)
    text = re.sub(r"\b(un|une|le|la|les|des|de|du|d|a|the)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


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
