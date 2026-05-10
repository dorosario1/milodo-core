import shlex
import subprocess
from pathlib import Path

from executor_profiles import (
    is_allowed,
    DEFAULT_PROFILE
)
from logger import log_info, log_warn, log_error


ALLOWED_COMMANDS = {
    "git",
    "python",
    "pip",
    "node",
    "npm",
    "docker",
    "docker-compose",
    "ollama"
}


def run_command(command, cwd=None, timeout=60, profile=DEFAULT_PROFILE):
    try:
        args = _to_args(command)
        log_info(f"Commande demandee: {args}")

        if not args:
            return _result(False, "", "Commande vide", 1)

        command_name = args[0]

        if command_name not in ALLOWED_COMMANDS:
            log_warn(f"Commande bloquee: {args}")
            return _result(False, "", "Commande non autorisée", 1)

        working_dir = Path(cwd) if cwd else None

        allowed, needs_confirmation = (
            is_allowed(
                command,
                profile
            )
        )

        if not allowed:

            return {
                "success": False,
                "error":
                    f"Commande "
                    f"'{command}' "
                    f"non autorisée "
                    f"(profil: {profile})",
                "stdout": "",
                "stderr": ""
            }

        if needs_confirmation:

            log_warn(
                f"Commande sensible "
                f"(profil={profile}) : "
                f"{command}"
            )

        completed = subprocess.run(
            args,
            cwd=str(working_dir) if working_dir else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )

        success = completed.returncode == 0
        log_info(f"Commande terminee: code {completed.returncode}")

        return _result(
            success,
            completed.stdout,
            completed.stderr,
            completed.returncode,
        )
    except subprocess.TimeoutExpired as error:
        log_error(f"Timeout commande apres {timeout}s")
        return _result(
            False,
            error.stdout or "",
            error.stderr or f"Timeout apres {timeout}s",
            -1,
        )
    except Exception as error:
        log_error(f"Erreur commande: {error}")
        return _result(False, "", str(error), 1)


def run_python(command):
    print("Execution Python demandee")
    return run_command(["python"] + _to_args(command))


def run_pip(command):
    print("Execution pip demandee")
    return run_command(["python", "-m", "pip"] + _to_args(command))


def run_npm(command):
    print("Execution npm demandee")
    return run_command(["npm"] + _to_args(command))


def run_git(command):
    print("Execution git demandee")
    return run_command(["git"] + _to_args(command))


def _to_args(command):
    if command is None:
        return []

    if isinstance(command, (list, tuple)):
        return [str(item) for item in command]

    if isinstance(command, str):
        return shlex.split(command, posix=False)

    return [str(command)]


def _result(success, stdout, stderr, return_code):
    return {
        "success": bool(success),
        "stdout": stdout or "",
        "stderr": stderr or "",
        "return_code": int(return_code),
    }
