import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


EXCLUDED_DIR_NAMES = {
    ".git",
    ".milodo",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
}

EXCLUDED_FILE_NAMES = {
    ".env",
}

EXCLUDED_FILE_PREFIXES = (
    ".env.",
)


def workspace_root():
    return Path(".milodo") / "workspaces"


def generate_workspace_id(project_name):
    safe_name = _safe_name(project_name or "workspace")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{safe_name}-{timestamp}"


def copy_project_tree(source_path, target_path):
    source = Path(source_path)
    target = Path(target_path)

    if not source.exists():
        raise FileNotFoundError(f"Source introuvable: {source}")

    if not source.is_dir():
        raise NotADirectoryError(f"Source invalide: {source}")

    target.mkdir(parents=True, exist_ok=True)

    try:
        items = list(source.iterdir())
    except PermissionError:
        print(f"[workspace_sandbox] Dossier ignoré (accès refusé) : {source}")
        return

    for item in items:
        if _should_exclude(item):
            continue

        destination = target / item.name

        if item.is_dir():
            copy_project_tree(item, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def write_meta(workspace_dir, meta):
    workspace_path = Path(workspace_dir)
    workspace_path.mkdir(parents=True, exist_ok=True)

    meta_path = workspace_path / "meta.json"
    with meta_path.open("w", encoding="utf-8") as file:
        json.dump(meta, file, indent=2, ensure_ascii=False)
        file.write("\n")


def load_meta(workspace_dir):
    meta_path = Path(workspace_dir) / "meta.json"

    with meta_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def create_workspace(source_project):
    if not isinstance(source_project, dict) or not source_project:
        raise ValueError("source_project invalide")

    source_name = source_project.get("name") or ""
    source_raw_path = source_project.get("path") or source_project.get("output_dir") or ""

    if not source_raw_path:
        raise ValueError("source_project doit contenir path ou output_dir")

    source_path = Path(source_raw_path).resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"Projet source introuvable: {source_path}")

    if not source_path.is_dir():
        raise NotADirectoryError(f"Projet source invalide: {source_path}")

    workspace_id = generate_workspace_id(source_name or source_path.name)
    root = workspace_root()
    workspace_dir = (root / workspace_id).resolve()
    project_dir = workspace_dir / "project"

    workspace_dir.mkdir(parents=True, exist_ok=True)
    copy_project_tree(source_path, project_dir)

    meta = {
        "workspace_id": workspace_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "source_project": {
            "name": source_project.get("name") or source_path.name,
            "path": str(source_path),
            "types": source_project.get("types", []),
        },
        "workspace": {
            "path": str(workspace_dir),
            "project_path": str(project_dir),
            "cwd": str(project_dir),
            "output_dir": str(project_dir),
        },
        "copy_policy": {
            "excluded_names": sorted(EXCLUDED_DIR_NAMES | EXCLUDED_FILE_NAMES),
            "excluded_prefixes": list(EXCLUDED_FILE_PREFIXES),
        },
    }

    write_meta(workspace_dir, meta)

    return {
        "workspace_id": workspace_id,
        "workspace_dir": str(workspace_dir),
        "meta": meta,
    }


def build_run_context(workspace_dir):
    workspace_path = Path(workspace_dir).resolve()
    meta = load_meta(workspace_path)

    workspace = meta.get("workspace", {})
    source_project = meta.get("source_project", {})

    return {
        "workspace_id": meta.get("workspace_id", ""),
        "workspace_path": str(workspace_path),
        "cwd": workspace.get("cwd", str(workspace_path / "project")),
        "output_dir": workspace.get("output_dir", str(workspace_path / "project")),
        "source_project": source_project,
        "meta": meta,
    }


def _safe_name(value):
    text = str(value or "").strip().lower()
    chars = []

    for char in text:
        if char.isalnum():
            chars.append(char)
        elif char in {" ", "-", "_"}:
            chars.append("-")

    safe = "".join(chars).strip("-")

    while "--" in safe:
        safe = safe.replace("--", "-")

    return safe or "workspace"


def _should_exclude(path):
    name = path.name

    if path.is_dir() and name in EXCLUDED_DIR_NAMES:
        return True

    if path.is_file() and name in EXCLUDED_FILE_NAMES:
        return True

    if path.is_file():
        for prefix in EXCLUDED_FILE_PREFIXES:
            if name.startswith(prefix):
                return True

    return False
