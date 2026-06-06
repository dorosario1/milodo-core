import logging
import shutil
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path
from skills.sandbox_workspace import SandboxWorkspace


LOG_PATH = Path(".milodo/executor.log")
BACKUPS_ROOT = Path(".milodo/backups")

ALLOWED_PREFIXES = [
    "npm install",
    "npm run build",
    "npm run dev",
    "pip install",
    "python",
    "git clone",
    "git pull",
    "mkdir",
    "cp",
    "mv",
]


def setup_logger():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("milodo_executor")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


LOGGER = setup_logger()


def is_command_allowed(command):
    normalized = str(command).strip().lower()
    return any(
        normalized == prefix or normalized.startswith(prefix + " ")
        for prefix in ALLOWED_PREFIXES
    )


def backup_file(file_path):
    source = Path(file_path)
    BACKUPS_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_ROOT / f"{timestamp}_{source.name}"

    if source.exists():
        shutil.copy2(source, backup_path)

    return str(backup_path)


def restore_backup(backup_path, original_path):
    backup = Path(backup_path)
    original = Path(original_path)

    if not backup.exists():
        return False

    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, original)
    return True


def execute_command(command, dry_run=True, timeout=30):
    start = time.time()

    if not is_command_allowed(command):
        LOGGER.warning("command denied: %s", command)
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command not allowed",
            "command": command,
            "return_code": -1,
            "dry_run": dry_run,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
        }

    if dry_run:
        LOGGER.info("dry-run command: %s", command)
        return {
            "success": True,
            "stdout": "[DRY RUN] Command not executed",
            "stderr": "",
            "command": command,
            "return_code": 0,
            "dry_run": True,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
        }

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=True,
            timeout=timeout,
        )
        success = result.returncode == 0
        LOGGER.info(
            "command executed: %s success=%s return_code=%s",
            command,
            success,
            result.returncode,
        )
        return {
            "success": success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": command,
            "return_code": result.returncode,
            "dry_run": False,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
        }
    except subprocess.TimeoutExpired as error:
        LOGGER.error("command timeout: %s", command)
        return {
            "success": False,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "Command timed out",
            "command": command,
            "return_code": -1,
            "dry_run": False,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
        }
    except Exception as error:
        LOGGER.error("command failed: %s error=%s", command, error)
        return {
            "success": False,
            "stdout": "",
            "stderr": str(error),
            "command": command,
            "return_code": -1,
            "dry_run": False,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
        }


def apply_patch(patch, dry_run=True):
    start = time.time()
    file_path = patch.get("file_path", "")
    content = patch.get("content", "")
    backup_path = None

    if dry_run:
        LOGGER.info("dry-run patch: %s", file_path)
        return {
            "success": True,
            "stdout": "[DRY RUN] Patch not applied",
            "stderr": "",
            "command": "patch",
            "return_code": 0,
            "dry_run": True,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
        }

    try:
        path = Path(file_path)
        backup_path = backup_file(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        LOGGER.info("patch applied: %s", file_path)
        return {
            "success": True,
            "stdout": "",
            "stderr": "",
            "command": "patch",
            "return_code": 0,
            "dry_run": False,
            "backup_path": backup_path,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
        }
    except Exception as error:
        rollback_triggered = False
        if backup_path:
            rollback_triggered = restore_backup(backup_path, file_path)
        LOGGER.error("patch failed: %s error=%s", file_path, error)
        return {
            "success": False,
            "stdout": "",
            "stderr": str(error),
            "command": "patch",
            "return_code": -1,
            "dry_run": False,
            "backup_path": backup_path,
            "rollback_triggered": rollback_triggered,
            "execution_time": round(time.time() - start, 4),
        }


def execute_fix(issue, patch, dry_run=True):
    patch_result = apply_patch(patch, dry_run=dry_run)
    result = dict(patch_result)
    result["issue"] = issue
    return result


def _sandbox_patch(original_html, patched_html, filename="index.html", dry_run=True):
    start = time.time()
    try:
        workspace = SandboxWorkspace()
        workspace_path = workspace.create_workspace()
        original_path = workspace.save_original_html(
            original_html,
            filename=filename,
        )

        result = {
            "success": True,
            "stdout": "",
            "stderr": "",
            "command": "sandbox_patch",
            "return_code": 0,
            "dry_run": dry_run,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": 0.0,
            "workspace_path": workspace_path,
            "original_path": original_path,
            "patched_path": None,
            "report": None,
        }

        if dry_run:
            LOGGER.info("dry-run sandbox patch workspace=%s", workspace_path)
        else:
            patched_path = workspace.apply_patch_to_workspace(
                patched_html,
                filename=filename,
            )
            report = workspace.generate_workspace_report()
            result["patched_path"] = patched_path
            result["report"] = report
            LOGGER.info("sandbox patch applied workspace=%s", workspace_path)

        result["execution_time"] = round(time.time() - start, 4)
        return result
    except Exception as error:
        LOGGER.exception("sandbox patch failed")
        return {
            "success": False,
            "stdout": "",
            "stderr": str(error),
            "command": "sandbox_patch",
            "return_code": -1,
            "dry_run": dry_run,
            "backup_path": None,
            "rollback_triggered": False,
            "execution_time": round(time.time() - start, 4),
            "message": f"Sandbox patch failed: {error}",
            "traceback": traceback.format_exc(),
        }


def run(action="command", **kwargs):
    if action == "command":
        return execute_command(
            command=kwargs.get("command", ""),
            dry_run=kwargs.get("dry_run", True),
            timeout=kwargs.get("timeout", 30),
        )

    if action == "patch":
        return apply_patch(
            patch=kwargs.get("patch", {}),
            dry_run=kwargs.get("dry_run", True),
        )

    if action == "execute_fix":
        return execute_fix(
            issue=kwargs.get("issue", {}),
            patch=kwargs.get("patch", {}),
            dry_run=kwargs.get("dry_run", True),
        )

    if action == "sandbox_patch":
        return _sandbox_patch(
            original_html=kwargs.get("original_html", ""),
            patched_html=kwargs.get("patched_html", ""),
            filename=kwargs.get("filename", "index.html"),
            dry_run=kwargs.get("dry_run", True),
        )

    return {
        "success": False,
        "error": f"Action inconnue: {action}",
    }
