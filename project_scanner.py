import json
import os
from pathlib import Path


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
    projects = []
    seen_paths = set()

    print("MILODO project scanner")
    print("Scan demarre")

    for root in get_scan_roots():
        if not root.exists():
            print(f"Dossier ignore, introuvable: {root}")
            continue

        if not root.is_dir():
            print(f"Chemin ignore, pas un dossier: {root}")
            continue

        print(f"Scan dossier: {root}")

        for current_path, dir_names, _file_names in os.walk(root):
            dir_names[:] = [
                name for name in dir_names
                if name not in IGNORED_DIRS and not name.startswith(".")
            ]

            directory = Path(current_path)

            try:
                project_types = detect_project_types(directory)
            except OSError as error:
                print(f"Dossier ignore, lecture impossible: {directory} ({error})")
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

            print(f"Projet detecte: {directory.name} [{', '.join(project_types)}]")

    projects.sort(key=lambda project: project["path"].lower())
    print(f"Scan termine: {len(projects)} projet(s) detecte(s)")

    return projects


def save_projects(projects):
    output_dir = Path(".milodo")
    output_file = output_dir / "projects.json"

    output_dir.mkdir(exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(projects, file, indent=2, ensure_ascii=False)
        file.write("\n")

    print(f"Resultats sauvegardes: {output_file}")


def main():
    projects = scan_projects()
    save_projects(projects)


if __name__ == "__main__":
    main()
