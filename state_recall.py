import json
from datetime import datetime, timezone
from pathlib import Path

from logger import log_info, log_error, log_warn, log_debug


MILODO_DIR = Path(".milodo")
PROJECTS_FILE = MILODO_DIR / "projects.json"
STATE_FILE = MILODO_DIR / "state.json"
PROJECTS_HISTORY_FILE = MILODO_DIR / "projects_history.json"
CURRENT_PROJECT_FILE = MILODO_DIR / "current_project.json"


def load_projects():
    if not PROJECTS_FILE.exists():
        log_warn(f"Fichier introuvable : {PROJECTS_FILE}")
        return []

    try:
        with PROJECTS_FILE.open("r", encoding="utf-8") as file:
            projects = json.load(file)

        if not isinstance(projects, list):
            log_warn(f"Format projets invalide: {PROJECTS_FILE}")
            return []

        log_info(f"Mémoire chargée : {len(projects)} projets")
        return projects
    except (OSError, json.JSONDecodeError) as error:
        log_error(f"Erreur lecture mémoire : {error}")
        return []


def save_state(state):
    try:
        MILODO_DIR.mkdir(exist_ok=True)

        with STATE_FILE.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, ensure_ascii=False)
            file.write("\n")

        log_debug("Mémoire sauvegardée")
    except OSError as error:
        log_error(f"Erreur lecture mémoire : {error}")
        raise


def load_state():
    if not STATE_FILE.exists():
        log_warn(f"Fichier introuvable : {STATE_FILE}")
        return _default_state()

    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            state = json.load(file)

        if not isinstance(state, dict):
            log_warn(f"Format etat invalide: {STATE_FILE}")
            return _default_state()

        state.setdefault("last_project", {})
        state.setdefault("updated_at", "")

        log_debug(f"Etat charge: {STATE_FILE}")
        return state
    except (OSError, json.JSONDecodeError) as error:
        log_error(f"Erreur lecture mémoire : {error}")
        return _default_state()


def find_project_by_name(name):
    search_name = str(name).lower()
    log_debug(f"Recherche projet : {name}")

    for project in load_projects():
        project_name = str(project.get("name", "")).lower()

        if project_name == search_name:
            log_debug(f"Projet trouve: {project.get('name', '')}")
            return project

    log_warn(f"Projet introuvable : {name}")
    return None


def find_projects_by_type(project_type):
    search_type = str(project_type).lower()
    log_debug(f"Recherche projet : {project_type}")
    matches = []

    for project in load_projects():
        project_types = project.get("types", [])

        if any(str(item).lower() == search_type for item in project_types):
            matches.append(project)

    if not matches:
        log_warn(f"Projet introuvable : {project_type}")
    log_debug(f"Projets trouves par type {project_type}: {len(matches)}")
    return matches


def remember_last_project(project):
    state = load_state()
    state["last_project"] = project or {}
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    try:
        project_data = project or {}
        history = []

        if PROJECTS_HISTORY_FILE.exists():
            loaded = json.loads(PROJECTS_HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                history = loaded

        output_dir = str(project_data.get("output_dir", ""))
        history = [
            item for item in history
            if str(item.get("output_dir", "")) != output_dir
        ]

        history.insert(0, project_data)
        history = history[:50]

        MILODO_DIR.mkdir(exist_ok=True)
        PROJECTS_HISTORY_FILE.write_text(
            json.dumps(history, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        log_warn(f"Impossible de sauvegarder l'historique projets : {error}")

    log_debug("Dernier projet memorise")


def list_projects():
    """
    Retourne tous les projets mémorisés,
    triés du plus récent au plus ancien.
    """

    try:
        if not PROJECTS_HISTORY_FILE.exists():
            return []

        projects = json.loads(
            PROJECTS_HISTORY_FILE.read_text(encoding="utf-8")
        )

        projects.sort(
            key=lambda x: x.get("date", ""),
            reverse=True
        )

        return projects

    except Exception:
        return []


def get_project(name):
    """
    Recherche un projet par nom.
    """

    projects = list_projects()

    for project in projects:
        if project.get("name", "").lower() == name.lower():
            return project

    for project in load_projects():
        if project.get("name", "").lower() == name.lower():
            return project

    return None


def set_current_project(name):
    """
    Définit le projet actif.
    """

    try:
        project = get_project(name)

        if not project:
            return {
                "success": False,
                "error": f"Projet introuvable : {name}"
            }

        MILODO_DIR.mkdir(exist_ok=True)

        CURRENT_PROJECT_FILE.write_text(
            json.dumps(project, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

        log_info(f"Projet actif changé : {name}")

        return {
            "success": True,
            "project": project
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_current_project():
    """
    Retourne le projet actif.
    """

    try:
        if not CURRENT_PROJECT_FILE.exists():
            return None

        return json.loads(
            CURRENT_PROJECT_FILE.read_text(encoding="utf-8")
        )

    except Exception:
        return None


def get_project_context(name):
    """
    Retourne le contexte complet d'un projet.

    Contexte = {
        "project": {...},
        "files": [...],
        "last_modified": "...",
        "is_current": True/False
    }
    """

    try:
        project = get_project(name)

        if not project:
            return {
                "error": "Projet introuvable"
            }

        files = []
        last_modified = None

        output_dir = project.get("output_dir")

        if output_dir:
            project_path = Path(output_dir)

            if project_path.exists():

                for item in project_path.rglob("*"):
                    if item.is_file():
                        files.append(str(item))

                try:
                    last_modified = datetime.fromtimestamp(
                        project_path.stat().st_mtime,
                        tz=timezone.utc
                    ).isoformat()
                except Exception:
                    last_modified = None

        current_project = get_current_project()

        is_current = False

        if current_project:
            is_current = (
                current_project.get("name", "").lower()
                == name.lower()
            )

        context = {
            "project": project,
            "files": files,
            "last_modified": last_modified,
            "is_current": is_current
        }

        log_info(f"Contexte projet chargé : {name}")

        return context

    except Exception as e:
        return {
            "error": str(e)
        }


def continue_project(name):
    """
    Reprend un projet existant : l'active et retourne son contexte complet.

    Retourne :
    {
        "success": True,
        "project": {...},
        "context": {...},
        "message": "Projet repris"
    }

    ou

    {
        "success": False,
        "error": "..."
    }
    """

    try:
        switch_result = set_current_project(name)

        if not switch_result.get("success"):
            return {
                "success": False,
                "error": switch_result.get(
                    "error",
                    "Impossible d'activer le projet"
                )
            }

        context = get_project_context(name)

        if context.get("error"):
            return {
                "success": False,
                "error": context.get("error")
            }

        log_info(f"Reprise projet : {name}")

        return {
            "success": True,
            "project": switch_result.get("project"),
            "context": context,
            "message": "Projet repris"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_last_project():
    state = load_state()
    last_project = state.get("last_project", {})

    if last_project:
        log_debug(f"Dernier projet: {last_project.get('name', '')}")
    else:
        log_warn("Aucun dernier projet memorise")

    return last_project


def _default_state():
    return {
        "last_project": {},
        "updated_at": "",
    }
