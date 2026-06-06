import difflib
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path


WORKSPACES_ROOT = Path(".milodo/workspaces")

LOGGER = logging.getLogger("milodo_sandbox_workspace")
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False

if not LOGGER.handlers:
    handler = logging.StreamHandler()
    LOGGER.addHandler(handler)


def flatten_backup_name(filename):
    return filename.replace("/", "__").replace("\\", "__")


def safe_read_text(path):
    raw = path.read_bytes()

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        LOGGER.warning(
            "latin-1 fallback for %s",
            path,
        )
        return raw.decode(
            "latin-1",
            errors="replace",
        )


def is_pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


class SandboxWorkspace:
    def __init__(self, workspace_id=None):
        self.workspace_id = workspace_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.root = WORKSPACES_ROOT / self.workspace_id
        self.original_dir = self.root / "original"
        self.patched_dir = self.root / "patched"
        self.backups_dir = self.root / "backups"
        self.reports_dir = self.root / "reports"
        self.lock_file = self.root / "workspace.lock"

    def create_workspace(self):
        if self.root.exists() and not self.is_lock_stale():
            return self.root

        for directory in (
            self.original_dir,
            self.patched_dir,
            self.backups_dir,
            self.reports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        if self.lock_file.exists():
            try:
                pid = int(self.lock_file.read_text(encoding="utf-8").strip())
                if is_pid_alive(pid):
                    LOGGER.warning("workspace already active")
            except Exception:
                pass

        self.lock_file.write_text(str(os.getpid()), encoding="utf-8")

        return self.root

    def is_lock_stale(self):
        if not self.lock_file.exists():
            return True

        try:
            pid = int(self.lock_file.read_text(encoding="utf-8").strip())
            return not is_pid_alive(pid)
        except Exception:
            return True

    def save_original_html(self, html, filename="index.html"):
        original_path = self.original_dir / filename
        backup_name = flatten_backup_name(filename)
        backup_path = self.backups_dir / f"{backup_name}.bak"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_text(html, encoding="utf-8")
        backup_path.write_text(html, encoding="utf-8")
        return str(original_path)

    def apply_patch_to_workspace(self, content, filename="index.html"):
        self.create_workspace()
        patched_path = self.patched_dir / filename
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_text(content, encoding="utf-8")
        return str(patched_path)

    def diff_workspace(self):
        original_files = {
            path.relative_to(self.original_dir): path
            for path in self.original_dir.rglob("*")
            if path.is_file()
        }
        patched_files = {
            path.relative_to(self.patched_dir): path
            for path in self.patched_dir.rglob("*")
            if path.is_file()
        }

        files_modified = []
        modified_lines = []
        patch_size = 0

        for relative_path in sorted(set(original_files) | set(patched_files)):
            original_text = (
                safe_read_text(original_files[relative_path])
                if relative_path in original_files
                else ""
            )
            patched_text = (
                safe_read_text(patched_files[relative_path])
                if relative_path in patched_files
                else ""
            )

            if original_text == patched_text:
                continue

            files_modified.append(str(relative_path))
            diff_lines = list(
                difflib.unified_diff(
                    original_text.splitlines(),
                    patched_text.splitlines(),
                    fromfile=f"original/{relative_path}",
                    tofile=f"patched/{relative_path}",
                    lineterm="",
                )
            )
            modified_lines.extend(diff_lines)
            patch_size += len([
                line for line in diff_lines
                if line.startswith("+") or line.startswith("-")
            ])

        return {
            "lines_modified": modified_lines,
            "files_modified": files_modified,
            "patch_size": patch_size,
        }

    def cleanup_workspace(self, dry_run=True):
        if dry_run and self.root.exists():
            resolved = self.root.resolve()
            shutil.rmtree(self.root)
            LOGGER.warning(
                "workspace deleted: %s",
                resolved,
            )
            return True
        return False

    def workspace_health(self):
        rollback_available = any(self.backups_dir.glob("*.bak"))
        workspace_size_bytes = sum(
            p.stat().st_size
            for p in self.root.rglob("*")
            if p.is_file()
        )
        workspace_size_mb = workspace_size_bytes / (1024 * 1024)
        stale_lock = False

        if self.lock_file.exists():
            try:
                pid = int(self.lock_file.read_text(encoding="utf-8").strip())
                stale_lock = not is_pid_alive(pid)
            except Exception:
                stale_lock = True

        score = 100

        if stale_lock:
            score -= 40

        if workspace_size_mb > 40:
            score -= 20

        if not rollback_available:
            score -= 10

        return {
            "stale_lock": stale_lock,
            "workspace_size_mb": round(workspace_size_mb, 2),
            "rollback_available": rollback_available,
            "health_score": max(0, score),
        }

    def generate_workspace_report(self):
        diff = self.diff_workspace()
        health = self.workspace_health()
        report = {
            "report_version": "5.0",
            "workspace_id": self.workspace_id,
            "files_modified": diff["files_modified"],
            "diff_size": diff["patch_size"],
            "rollback_available": health["rollback_available"],
            "workspace_size_bytes": sum(
                p.stat().st_size
                for p in self.root.rglob("*")
                if p.is_file()
            ),
            "health_score": health["health_score"],
        }
        report_path = self.reports_dir / "workspace_report.json"
        report_path.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        return report


def create_workspace():
    workspace = SandboxWorkspace()
    workspace.create_workspace()
    return workspace


def save_original_html(html, workspace=None, filename="index.html"):
    workspace = workspace or create_workspace()
    return workspace.save_original_html(html, filename=filename)


def apply_patch_to_workspace(content, workspace=None, filename="index.html"):
    workspace = workspace or create_workspace()
    return workspace.apply_patch_to_workspace(content, filename=filename)


def diff_workspace(workspace):
    return workspace.diff_workspace()


def cleanup_workspace(workspace, dry_run=True):
    return workspace.cleanup_workspace(dry_run=dry_run)


def generate_workspace_report(workspace):
    return workspace.generate_workspace_report()
