import importlib.util
import py_compile
import re
from pathlib import Path

from logger import log_info, log_error, log_warn, log_debug


SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def scan_skills():
    log_debug(f"Scan skills: {SKILLS_DIR}")

    if not SKILLS_DIR.exists():
        log_warn("Dossier skills introuvable")
        return []

    skill_files = []

    for skill_path in sorted(SKILLS_DIR.glob("*.py")):
        if skill_path.name == "__init__.py":
            continue

        if skill_path.name.endswith(".disabled"):
            log_debug(f"Skill désactivé ignoré : {skill_path.stem}")
            continue

        disabled_marker = skill_path.with_name(f"{skill_path.name}.disabled")
        if disabled_marker.exists():
            log_debug(f"Skill désactivé ignoré : {skill_path.stem}")
            continue

        skill_files.append(skill_path)

    log_info(f"Scan skills : {len(skill_files)} trouvés")
    return skill_files


def validate_skill(module):
    log_debug("Validation skill")
    missing = []

    if not hasattr(module, "SKILL_NAME"):
        missing.append("SKILL_NAME")

    if not hasattr(module, "SKILL_DESCRIPTION"):
        missing.append("SKILL_DESCRIPTION")

    if missing:
        return {
            "valid": False,
            "missing": missing,
        }

    return {
        "valid": True,
        "name": str(module.SKILL_NAME),
        "description": str(module.SKILL_DESCRIPTION),
    }


def load_skill(skill_path):
    path = Path(skill_path)
    name = path.stem
    log_debug(f"Chargement skill: {path}")

    if not path.exists():
        log_warn(f"Skill invalide ignoré : {name}")
        return {
            "success": False,
            "path": str(path),
            "error": "Fichier introuvable",
        }

    if path.name == "__init__.py" or path.suffix != ".py":
        log_warn(f"Skill invalide ignoré : {name}")
        return {
            "success": False,
            "path": str(path),
            "error": "Fichier skill invalide",
        }

    try:
        module_name = f"skills.{path.stem}"
        log_debug(f"Validation import : {module_name}")
        spec = importlib.util.spec_from_file_location(module_name, path)

        if spec is None or spec.loader is None:
            log_warn(f"Skill invalide ignoré : {name}")
            return {
                "success": False,
                "path": str(path),
                "error": "Spec importlib invalide",
            }

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        validation = validate_skill(module)

        if not validation.get("valid"):
            log_warn(f"Skill invalide ignoré : {name}")
            return {
                "success": False,
                "path": str(path),
                "error": "Structure skill invalide",
                "missing": validation.get("missing", []),
            }

        log_info(f"Skill chargé : {validation['name']}")
        return {
            "success": True,
            "path": str(path),
            "name": validation["name"],
            "description": validation["description"],
            "module": module,
        }
    except Exception as error:
        log_error(f"Erreur chargement {name} : {error}")
        return {
            "success": False,
            "path": str(path),
            "error": str(error),
        }


def load_all_skills():
    log_debug("Chargement toutes les skills")

    result = {
        "loaded": [],
        "invalid": [],
        "errors": [],
    }

    for skill_path in scan_skills():
        loaded_skill = load_skill(skill_path)

        if loaded_skill.get("success"):
            result["loaded"].append({
                "name": loaded_skill["name"],
                "description": loaded_skill["description"],
                "path": loaded_skill["path"],
            })
            continue

        if loaded_skill.get("missing"):
            result["invalid"].append(loaded_skill)
        else:
            result["errors"].append(loaded_skill)

    log_info(
        "Chargement termine: "
        f"{len(result['loaded'])} chargee(s), "
        f"{len(result['invalid'])} invalide(s), "
        f"{len(result['errors'])} erreur(s)"
    )

    return result


def list_skills():
    return load_all_skills().get("loaded", [])


def create_skill(name, description, code):
    log_info(f"Creation skill demandee: {name}")

    try:
        if not re.fullmatch(r"[A-Za-z0-9_]+", str(name or "")):
            return {
                "success": False,
                "path": None,
                "error": "Nom invalide: lettres, chiffres et underscore uniquement",
            }

        skill_path = SKILLS_DIR / f"{name}.py"

        if skill_path.exists():
            return {
                "success": False,
                "path": str(skill_path),
                "error": "Skill deja existante",
            }

        content = (
            f"SKILL_NAME = {name!r}\n"
            f"SKILL_DESCRIPTION = {description!r}\n"
            "SKILL_VERSION = \"1.0.0\"\n\n"
            f"{code.rstrip()}\n"
        )

        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(content, encoding="utf-8")

        try:
            log_debug(f"Validation syntaxe : {skill_path}")
            py_compile.compile(str(skill_path), doraise=True)
        except py_compile.PyCompileError as error:
            try:
                skill_path.unlink()
            except OSError:
                pass

            return {
                "success": False,
                "path": str(skill_path),
                "error": f"Syntaxe Python invalide: {error.msg}",
            }

        load_result = load_all_skills()

        for loaded_skill in load_result.get("loaded", []):
            if loaded_skill.get("name") == name:
                log_info(f"Skill créé : {name}")
                return {
                    "success": True,
                    "path": str(skill_path),
                    "error": None,
                }

        return {
            "success": False,
            "path": str(skill_path),
            "error": "Skill creee mais non chargee",
        }
    except OSError as error:
        return {
            "success": False,
            "path": str(SKILLS_DIR / f"{name}.py"),
            "error": f"Erreur ecriture: {error}",
        }
    except Exception as error:
        return {
            "success": False,
            "path": str(SKILLS_DIR / f"{name}.py"),
            "error": str(error),
        }
