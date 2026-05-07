import json
from datetime import datetime, timezone
from pathlib import Path

from logger import log_info, log_error, log_warn, log_debug


MILODO_DIR = Path(".milodo")
PROJECTS_FILE = MILODO_DIR / "projects.json"
STATE_FILE = MILODO_DIR / "state.json"


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
    log_debug("Dernier projet memorise")


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
