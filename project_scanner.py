import json
import os
import time
from pathlib import Path

from logger import log_info, log_error, log_warn, log_debug


PROJECT_MARKERS = {
    "NodeJS": ["package.json"],
    "Python": ["requirements.txt", "pyproject.toml"],
    "Docker": ["Dockerfile", "docker-compose.yml"],
    "Shopify": ["shopify.config.toml"],
    "HTML": ["index.html"],
}

IGNORED_DIRS = {
    ".git",
    ".milodo",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
}


def get_scan_roots():
    home = Path.home()
    return [
        home / "Desktop",
        home / "Documents",
        home / "projects",
    ]


def detect_project_types(directory):
    found_files = {item.name for item in directory.iterdir() if item.is_file()}
    project_types = []

    for project_type, markers in PROJECT_MARKERS.items():
        if any(marker in found_files for marker in markers):
            project_types.append(project_type)

    return project_types


def scan_projects():
    start_time = time.perf_counter()
    projects = []
    seen_paths = set()

    log_debug("MILODO project scanner")
    log_info("Scan démarré")

    for root in get_scan_roots():
        if not root.exists():
            log_warn(f"Dossier introuvable : {root}")
            continue

        if not root.is_dir():
            log_warn(f"Dossier introuvable : {root}")
            continue

        log_debug(f"Scan dossier : {root}")

        for current_path, dir_names, _file_names in os.walk(root):
            dir_names[:] = [
                name for name in dir_names
                if name not in IGNORED_DIRS and not name.startswith(".")
            ]

            directory = Path(current_path)

            try:
                project_types = detect_project_types(directory)
            except OSError as error:
                log_error(f"Erreur lecture : {directory}")
                continue

            if not project_types:
                continue

            resolved_path = str(directory.resolve())

            if resolved_path in seen_paths:
                continue

            seen_paths.add(resolved_path)
            projects.append({
                "name": directory.name,
                "path": resolved_path,
                "types": project_types,
            })

            log_info(f"Projet : {directory.name} [{', '.join(project_types)}]")

    projects.sort(key=lambda project: project["path"].lower())
    ms = int((time.perf_counter() - start_time) * 1000)
    log_info(f"Scan terminé : {len(projects)} projet(s)")
    log_debug(f"Scan terminé en {ms}ms")

    return projects


def save_projects(projects):
    output_dir = Path(".milodo")
    output_file = output_dir / "projects.json"

    output_dir.mkdir(exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(projects, file, indent=2, ensure_ascii=False)
        file.write("\n")

    log_info(f"Resultats sauvegardes: {output_file}")


def main():
    projects = scan_projects()
    save_projects(projects)


if __name__ == "__main__":
    main()
