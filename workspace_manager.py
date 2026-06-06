from datetime import datetime, timezone
from pathlib import Path

import state_recall


def load_project_inventory():
    projects = state_recall.load_projects()

    if not isinstance(projects, list):
        return []

    return projects


def resolve_workspace(project_name=None):
    if project_name:
        project = state_recall.get_project(project_name)

        if project:
            return project

        for item in load_project_inventory():
            if str(item.get("name", "")).lower() == str(project_name).lower():
                return item

        return None

    current_project = state_recall.get_current_project()
    if isinstance(current_project, dict) and current_project:
        return current_project

    last_project = state_recall.get_last_project()
    if isinstance(last_project, dict) and last_project:
        return last_project

    projects = load_project_inventory()
    if projects:
        return projects[0]

    return None


def workspace_exists(workspace):
    if not isinstance(workspace, dict):
        return False

    workspace_path = workspace.get("path") or workspace.get("output_dir")
    if not workspace_path:
        return False

    return Path(workspace_path).exists()


def build_workspace_context(workspace):
    if not isinstance(workspace, dict) or not workspace:
        return {
            "project": {},
            "cwd": "",
            "output_dir": "",
            "name": "",
            "path": "",
            "types": [],
            "git_enabled": False,
            "activated_at": "",
            "source": "state_recall",
        }

    workspace_path = workspace.get("path") or workspace.get("output_dir") or ""
    resolved_path = ""

    if workspace_path:
        try:
            resolved_path = str(Path(workspace_path).resolve())
        except OSError:
            resolved_path = str(workspace_path)

    types = workspace.get("types", [])
    if not isinstance(types, list):
        types = []

    git_enabled = "git" in {str(item).lower() for item in types}
    if resolved_path and (Path(resolved_path) / ".git").is_dir():
        git_enabled = True

    name = workspace.get("name") or (Path(resolved_path).name if resolved_path else "")

    return {
        "project": workspace,
        "cwd": resolved_path,
        "output_dir": resolved_path,
        "name": name,
        "path": resolved_path,
        "types": types,
        "git_enabled": git_enabled,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "source": "state_recall",
    }


def activate_workspace(workspace):
    context = build_workspace_context(workspace)
    project_name = context.get("name", "")

    if not project_name:
        return {
            "success": False,
            "error": "Workspace invalide",
            "context": context,
        }

    result = state_recall.set_current_project(project_name)

    return {
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "project": result.get("project"),
        "context": context,
    }


def prepare_run_context(goal, project_name=None):
    workspace = resolve_workspace(project_name)

    if not workspace:
        return {
            "success": False,
            "goal": goal,
            "error": "Aucun projet disponible",
            "workspace": None,
            "context": build_workspace_context({}),
        }

    context = build_workspace_context(workspace)

    if not workspace_exists(workspace):
        return {
            "success": False,
            "goal": goal,
            "error": f"Workspace introuvable : {context.get('path', '')}",
            "workspace": workspace,
            "context": context,
        }

    activation = activate_workspace(workspace)

    return {
        "success": bool(activation.get("success")),
        "goal": goal,
        "error": activation.get("error"),
        "workspace": workspace,
        "context": activation.get("context", context),
    }
