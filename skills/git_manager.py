SKILL_NAME = "git_manager"
SKILL_DESCRIPTION = "Gestion Git : init, add, commit, push, status"
SKILL_VERSION = "1.0.0"

from executor import run_command


def run(action, **kwargs):
    try:
        command = _build_command(action, **kwargs)
        result = run_command(command, cwd=kwargs.get("cwd"))

        return {
            "success": result.get("success", False),
            "output": result.get("stdout", ""),
            "error": result.get("stderr", ""),
        }
    except Exception as error:
        return {
            "success": False,
            "output": "",
            "error": str(error),
        }


def _build_command(action, **kwargs):
    action_name = str(action or "").strip().lower()

    if action_name == "init":
        return ["git", "init"]

    if action_name == "add":
        files = kwargs.get("files")

        if files:
            if isinstance(files, (list, tuple)):
                return ["git", "add"] + [str(item) for item in files]

            return ["git", "add", str(files)]

        return ["git", "add", "."]

    if action_name == "commit":
        message = kwargs.get("message")

        if not message:
            raise ValueError("message est requis pour commit")

        return ["git", "commit", "-m", str(message)]

    if action_name == "push":
        remote = kwargs.get("remote", "origin")
        branch = kwargs.get("branch", "main")
        return ["git", "push", str(remote), str(branch)]

    if action_name == "status":
        return ["git", "status"]

    if action_name == "remote_add":
        url = kwargs.get("url")

        if not url:
            raise ValueError("url est requis pour remote_add")

        remote = kwargs.get("remote", "origin")
        return ["git", "remote", "add", str(remote), str(url)]

    raise ValueError(f"Action Git inconnue: {action}")
