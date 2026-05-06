import json
from datetime import datetime, timezone
from pathlib import Path


MILODO_DIR = Path(".milodo")
PROJECTS_FILE = MILODO_DIR / "projects.json"
STATE_FILE = MILODO_DIR / "state.json"


def load_projects():
    if not PROJECTS_FILE.exists():
        print(f"Fichier projets introuvable: {PROJECTS_FILE}")
        return []

    try:
        with PROJECTS_FILE.open("r", encoding="utf-8") as file:
            projects = json.load(file)

        if not isinstance(projects, list):
            print(f"Format projets invalide: {PROJECTS_FILE}")
            return []

        print(f"Projets charges: {len(projects)}")
        return projects
    except (OSError, json.JSONDecodeError) as error:
        print(f"Erreur chargement projets: {PROJECTS_FILE} ({error})")
        return []


def save_state(state):
    try:
        MILODO_DIR.mkdir(exist_ok=True)

        with STATE_FILE.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, ensure_ascii=False)
            file.write("\n")

        print(f"Etat sauvegarde: {STATE_FILE}")
    except OSError as error:
        print(f"Erreur sauvegarde etat: {STATE_FILE} ({error})")
        raise


def load_state():
    if not STATE_FILE.exists():
        print(f"Fichier etat introuvable: {STATE_FILE}")
        return _default_state()

    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            state = json.load(file)

        if not isinstance(state, dict):
            print(f"Format etat invalide: {STATE_FILE}")
            return _default_state()

        state.setdefault("last_project", {})
        state.setdefault("updated_at", "")

        print(f"Etat charge: {STATE_FILE}")
        return state
    except (OSError, json.JSONDecodeError) as error:
        print(f"Erreur chargement etat: {STATE_FILE} ({error})")
        return _default_state()


def find_project_by_name(name):
    search_name = str(name).lower()

    for project in load_projects():
        project_name = str(project.get("name", "")).lower()

        if project_name == search_name:
            print(f"Projet trouve: {project.get('name', '')}")
            return project

    print(f"Projet introuvable: {name}")
    return None


def find_projects_by_type(project_type):
    search_type = str(project_type).lower()
    matches = []

    for project in load_projects():
        project_types = project.get("types", [])

        if any(str(item).lower() == search_type for item in project_types):
            matches.append(project)

    print(f"Projets trouves par type {project_type}: {len(matches)}")
    return matches


def remember_last_project(project):
    state = load_state()
    state["last_project"] = project or {}
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print("Dernier projet memorise")


def get_last_project():
    state = load_state()
    last_project = state.get("last_project", {})

    if last_project:
        print(f"Dernier projet: {last_project.get('name', '')}")
    else:
        print("Aucun dernier projet memorise")

    return last_project


def _default_state():
    return {
        "last_project": {},
        "updated_at": "",
    }
