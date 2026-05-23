from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
READ_ONLY_KUBECTL = {"get", "logs", "describe", "events"}


@dataclass
class RuntimeContext:
    runtime: str = "docker"
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])

    @property
    def pattern_root(self) -> Path:
        return self.root / "patterns"

    @property
    def log_root(self) -> Path:
        return self.root / "logs"

    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def load_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if "schema_version" not in data:
            raise ValueError(f"Missing schema_version in {path}")
        return data

    def run_docker_read(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if not args:
            raise ValueError("docker command requires arguments")
        if args[0] in {"rm", "rmi", "stop", "kill", "restart", "compose"}:
            raise ValueError("destructive docker commands are not allowed")
        return self._run(["docker", *args])

    def run_kubectl_read(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if not args or args[0] not in READ_ONLY_KUBECTL:
            raise ValueError("kubectl is restricted to get/logs/describe/events")
        return self._run(["kubectl", *args])

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        if shutil.which(command[0]) is None:
            return subprocess.CompletedProcess(command, 127, "", f"{command[0]} not found")
        return subprocess.run(command, capture_output=True, text=True, check=False)


def healthcheck(root: Path | None = None) -> dict[str, Any]:
    context = RuntimeContext(root=root or Path(__file__).resolve().parents[1])
    required = [
        context.root / "core",
        context.root / "patterns",
        context.root / "memory",
        context.root / "logs",
        context.root / "tests",
        context.root / "patterns" / "resource_exhaustion",
    ]
    missing = [str(path.relative_to(context.root)) for path in required if not path.exists()]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if not missing else "degraded",
        "missing": missing,
        "runtime": context.runtime,
        "timestamp": context.now(),
    }

