SKILL_NAME = "watchdog"
SKILL_DESCRIPTION = "Surveille le learning loop et le relance en cas de crash, avec anti-fork bomb et auto-résilience"
SKILL_VERSION = "1.0.0"

import json
import time
import os
import subprocess
from datetime import datetime
from pathlib import Path
from logger import log_info, log_error, log_warn


class Watchdog:
    def __init__(self):
        self.heartbeat_file = Path(".milodo/heartbeat.json")
        self.pid_file = Path(".milodo/scheduler.pid")
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        self.max_silence_minutes = 5

    def _read_heartbeat(self):
        try:
            data = json.loads(self.heartbeat_file.read_text(encoding="utf-8"))
            return datetime.fromisoformat(data["last_beat"])
        except Exception:
            return None

    def _is_scheduler_alive(self):
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                os.kill(pid, 0)
                return True
            except Exception:
                return False
        return False

    def _is_heartbeat_fresh(self):
        last = self._read_heartbeat()
        if last is None:
            return False
        silence = (datetime.now() - last).total_seconds() / 60
        return silence < self.max_silence_minutes

    def check_heartbeat(self):
        return {
            "alive": self._is_scheduler_alive() and self._is_heartbeat_fresh(),
            "scheduler_pid": self._is_scheduler_alive(),
            "heartbeat_fresh": self._is_heartbeat_fresh()
        }

    def _launch_scheduler(self):
        if self._is_scheduler_alive() and not self._is_heartbeat_fresh():
            log_warn("Scheduler bloqué détecté, nettoyage PID")
            self.pid_file.unlink(missing_ok=True)

        if self._is_scheduler_alive():
            log_warn("Scheduler déjà vivant, pas de relance")
            return

        log_info("Lancement scheduler")
        proc = subprocess.Popen(
            ["python", "-c", "from skills.learning_loop import run; run('schedule', interval=6)"],
            cwd=".",
            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
        )
        self.pid_file.write_text(str(proc.pid))

    def watch(self, check_interval_seconds=60):
        log_info("Watchdog démarré (intervalle: {}s)".format(check_interval_seconds))
        while True:
            try:
                if not self._is_scheduler_alive() or not self._is_heartbeat_fresh():
                    log_warn("Scheduler muet ou mort → relance")
                    self._launch_scheduler()
            except Exception as e:
                log_error("Watchdog error: {}".format(e))
            time.sleep(check_interval_seconds)


def run(action="watch", **kwargs):
    w = Watchdog()
    if action == "watch":
        w.watch()
    elif action == "check":
        return w.check_heartbeat()
    else:
        return {"success": False, "error": "Action inconnue: {}".format(action)}
