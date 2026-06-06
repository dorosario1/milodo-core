import json
import logging
import os
import sys
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from skills.autonomous_loop import run_autonomous_loop
from skills.queue_system import (
    enqueue_job,
    get_job_status,
    get_all_jobs,
    get_queue_metrics,
    get_worker_status,
    start_worker,
)


HOST = "127.0.0.1"
PORT = 8520
SERVER_START_TIME = time.time()
LOGGER = logging.getLogger("milodo_api")

# History storage (append-only, runtime-only)
MAX_HISTORY = 100
HISTORY: list = []
REQUEST_COUNTER = 0

# Metrics counters (runtime-only, append-only)
METRICS = {
    "total_requests": 0,
    "total_corrections": 0,
    "total_errors": 0,
    "total_health_checks": 0,
    "total_benchmark_runs": 0,
    "total_score_improvement": 0.0,
    "total_iterations_sum": 0,
    "total_rollbacks": 0,
}


def _check_core_modules() -> dict:
    modules = {}

    for name in (
        "audit_engine",
        "patch_generator",
        "orchestrator",
        "autonomous_loop",
        "sandbox_workspace",
        "reaudit_engine",
        "executor",
    ):
        try:
            __import__(f"skills.{name}")
            modules[name] = True
        except ImportError:
            modules[name] = False

    return modules


def _get_valid_api_keys() -> set:
    """
    Return configured API keys from env.
    """

    keys_env = os.environ.get(
        "MILODO_API_KEYS",
        "",
    ).strip()

    if not keys_env:
        return set()

    return {
        k.strip()
        for k in keys_env.split(",")
        if k.strip()
    }


def _get_benchmark_report() -> dict:
    """Read the last benchmark report if it exists."""
    report_path = Path(".milodo/benchmark_report.json")

    if not report_path.exists():
        return {
            "service": "MILODO API",
            "available": False,
            "message": (
                "No benchmark report found. "
                "Run POST /benchmark/run or "
                "python tests/test_benchmark_regression.py"
            ),
        }

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "service": "MILODO API",
            "available": True,
            "report_path": str(report_path.resolve()),
            "timestamp": data.get("timestamp"),
            "summary": data.get("summary", {}),
            "cases": data.get("cases", []),
        }

    except Exception as e:
        return {
            "service": "MILODO API",
            "available": False,
            "error": str(e),
        }


def _run_benchmark() -> dict:
    """Execute benchmark regression suite."""
    try:
        from tests.test_benchmark_regression import run_benchmark

        result = run_benchmark()

        return {
            "service": "MILODO API",
            "executed": True,
            "summary": result.get("summary", {}),
            "cases": result.get("cases", []),
            "report_path": str(
                Path(".milodo/benchmark_report.json").resolve()
            ),
        }

    except Exception as e:
        return {
            "service": "MILODO API",
            "executed": False,
            "error": str(e),
        }


def _get_metrics() -> dict:
    corrections = METRICS["total_corrections"]

    return {
        "service": "MILODO API",
        "total_requests": METRICS["total_requests"],
        "total_corrections": corrections,
        "total_errors": METRICS["total_errors"],
        "total_health_checks": METRICS["total_health_checks"],
        "total_benchmark_runs": METRICS["total_benchmark_runs"],
        "avg_score_improvement": round(
            METRICS["total_score_improvement"] / corrections,
            1,
        ) if corrections > 0 else 0.0,
        "avg_iterations": round(
            METRICS["total_iterations_sum"] / corrections,
            1,
        ) if corrections > 0 else 0.0,
        "rollback_rate": round(
            METRICS["total_rollbacks"] / corrections,
            2,
        ) if corrections > 0 else 0.0,
        "convergence_rate": round(
            (corrections - METRICS["total_rollbacks"]) / corrections,
            2,
        ) if corrections > 0 else 1.0,
        "uptime_seconds": round(
            time.time() - SERVER_START_TIME,
            1,
        ),
    }


def _workspace_health_score(
    has_lock: bool,
    lock_stale: bool,
    has_backups: bool,
) -> int:
    """Simple health score for a workspace."""

    if not has_lock:
        return 0

    if lock_stale:
        return 25

    if not has_backups:
        return 75

    return 100


def _get_workspaces(name_filter: str = None) -> dict:
    """List sandbox workspaces with metadata."""

    ws_root = Path(".milodo/workspaces")

    if not ws_root.exists():
        return {
            "service": "MILODO API",
            "workspaces_root": str(ws_root),
            "total_workspaces": 0,
            "active_workspaces": 0,
            "stale_workspaces": 0,
            "total_size_mb": 0.0,
            "workspaces": [],
        }

    workspaces = []
    total_size = 0
    active_count = 0
    stale_count = 0

    for ws_dir in sorted(
        ws_root.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        if not ws_dir.is_dir():
            continue

        if name_filter and ws_dir.name != name_filter:
            continue

        ws_size = sum(
            f.stat().st_size
            for f in ws_dir.rglob("*")
            if f.is_file()
        )

        total_size += ws_size

        lock_path = ws_dir / "workspace.lock"

        has_lock = lock_path.exists()
        lock_stale = False

        if has_lock:
            try:
                from skills.sandbox_workspace import SandboxWorkspace

                ws = SandboxWorkspace(ws_dir.name)
                lock_stale = ws.is_lock_stale()

            except Exception:
                lock_stale = False

        if lock_stale:
            stale_count += 1
        else:
            active_count += 1

        original_dir = ws_dir / "original"
        patched_dir = ws_dir / "patched"
        backups_dir = ws_dir / "backups"
        reports_dir = ws_dir / "reports"

        has_original = (
            original_dir.exists()
            and bool(list(original_dir.rglob("*")))
        )

        has_patched = (
            patched_dir.exists()
            and bool(list(patched_dir.rglob("*")))
        )

        has_backups = backups_dir.exists()

        backups_count = (
            len(list(backups_dir.rglob("*.bak")))
            if has_backups else 0
        )

        has_report = (
            reports_dir / "workspace_report.json"
        ).exists()

        workspaces.append({
            "name": ws_dir.name,
            "path": str(ws_dir),
            "size_mb": round(
                ws_size / (1024 * 1024),
                3,
            ),
            "has_lock": has_lock,
            "lock_stale": lock_stale,
            "has_original": has_original,
            "has_patched": has_patched,
            "has_backups": has_backups,
            "has_report": has_report,
            "backups_count": backups_count,
            "health_score": _workspace_health_score(
                has_lock,
                lock_stale,
                has_backups,
            ),
        })

        if name_filter:
            break

    return {
        "service": "MILODO API",
        "workspaces_root": str(ws_root.resolve()),
        "total_workspaces": (
            len(workspaces)
            if not name_filter
            else (1 if workspaces else 0)
        ),
        "active_workspaces": active_count,
        "stale_workspaces": stale_count,
        "total_size_mb": round(
            total_size / (1024 * 1024),
            3,
        ),
        "workspaces": workspaces,
    }


class MILODOHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _is_localhost(self) -> bool:
        """
        Check if request comes from localhost.
        """

        client_host = self.client_address[0]

        return client_host in (
            "127.0.0.1",
            "::1",
            "localhost",
        )

    def _auth_required(
        self,
        method: str,
        path: str,
    ) -> bool:
        """
        Determine whether auth is required.
        """

        valid_keys = _get_valid_api_keys()

        # Auth disabled
        if not valid_keys:
            return False

        # Public endpoints
        public_paths = (
            "/",
            "/health",
            "/dashboard",
        )

        if path in public_paths:
            return False

        # Localhost bypass
        bypass = os.environ.get(
            "MILODO_AUTH_BYPASS_LOCALHOST",
            "true",
        ).lower() == "true"

        if bypass and self._is_localhost():
            return False

        return True

    def _check_auth(self) -> bool:
        """
        Validate X-API-Key header.
        """

        valid_keys = _get_valid_api_keys()

        # Auth disabled
        if not valid_keys:
            return True

        api_key = self.headers.get(
            "X-API-Key",
            "",
        )

        return api_key in valid_keys

    def _send_unauthorized(self):
        """
        Send 401 Unauthorized response.
        """

        self._send_json(
            {
                "success": False,
                "error": (
                    "Unauthorized — "
                    "valid X-API-Key required"
                ),
                "message": (
                    "Set X-API-Key header "
                    "with a valid API key."
                ),
            },
            status=401,
        )

    def _serve_dashboard(self):
        """Serve the MILODO dashboard HTML page."""

        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MILODO Dashboard</title>
<style>
:root { --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #c9d1d9; --green: #3fb950; --red: #f85149; --blue: #58a6ff; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; }
h1, h2 { margin-top: 0; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.badge { padding: 6px 12px; border-radius: 999px; font-weight: bold; background: var(--green); color: #fff; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }
.metric-value { font-size: 2rem; font-weight: bold; margin-top: 10px; }
.metric-label { opacity: 0.8; }
.section { margin-bottom: 24px; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--border); padding: 10px; text-align: left; font-size: 0.9rem; }
th { color: var(--blue); }
.status-ok { color: var(--green); font-weight: bold; }
.status-bad { color: var(--red); font-weight: bold; }
.two-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.workspace { padding: 10px 0; border-bottom: 1px solid var(--border); }
.footer { margin-top: 30px; opacity: 0.7; font-size: 0.9rem; }
code { font-family: Consolas, monospace; }
@media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, 1fr); } .two-cols { grid-template-columns: 1fr; } }
@media (max-width: 700px) { .grid { grid-template-columns: 1fr; } body { padding: 12px; } }
</style>
</head>
<body>
<div class="header"><div><h1>MILODO Dashboard</h1><div id="uptime">Loading uptime...</div></div><div class="badge" id="statusBadge">HEALTHY</div></div>
<div class="grid">
<div class="card"><div class="metric-label">Total Corrections</div><div class="metric-value" id="totalCorrections">0</div></div>
<div class="card"><div class="metric-label">Avg Score Improvement</div><div class="metric-value" id="avgImprovement">0</div></div>
<div class="card"><div class="metric-label">Rollback Rate</div><div class="metric-value" id="rollbackRate">0</div></div>
<div class="card"><div class="metric-label">Convergence Rate</div><div class="metric-value" id="convergenceRate">0</div></div>
</div>
<div class="section card"><h2>Execution History</h2><table><thead><tr><th>ID</th><th>Timestamp</th><th>Improvement</th><th>Iterations</th><th>Status</th></tr></thead><tbody id="historyTable"></tbody></table></div>
<div class="two-cols"><div class="card"><h2>Benchmark</h2><div id="benchmarkContent">Loading benchmark...</div></div><div class="card"><h2>Workspaces</h2><div id="workspaceList">Loading workspaces...</div></div></div>
<h2 style="color:#58a6ff;margin-top:30px;">Queue</h2>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:15px 0;">
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Taille queue</div><div id="queue-size" style="font-size:28px;font-weight:bold;color:#58a6ff;">-</div></div>
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Jobs traités</div><div id="queue-processed" style="font-size:28px;font-weight:bold;color:#3fb950;">-</div></div>
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;"><div style="color:#8b949e;font-size:12px;text-transform:uppercase;">Durée moyenne</div><div id="queue-avg-duration" style="font-size:28px;font-weight:bold;color:#d2991d;">-</div></div>
</div>
<h2 style="color:#58a6ff;margin-top:20px;">Derniers Jobs</h2>
<table id="jobs-table" style="width:100%;border-collapse:collapse;margin:15px 0;font-size:13px;"><thead><tr style="background:#161b22;"><th style="padding:10px;border:1px solid #30363d;text-align:left;">ID</th><th style="padding:10px;border:1px solid #30363d;text-align:left;">Statut</th><th style="padding:10px;border:1px solid #30363d;text-align:left;">Score</th><th style="padding:10px;border:1px solid #30363d;text-align:left;">Durée</th></tr></thead><tbody id="jobs-tbody"></tbody></table>
<div class="footer">Auto-refresh in <span id="countdown">5</span>s</div>
<script>
let countdown = 5;
async function fetchJSON(url) { const response = await fetch(url); return await response.json(); }
async function fetchData() { const [health, metrics, history, benchmark, workspaces] = await Promise.all([fetchJSON('/health'), fetchJSON('/metrics'), fetchJSON('/history'), fetchJSON('/benchmark'), fetchJSON('/workspaces')]); return { health, metrics, history, benchmark, workspaces }; }
function renderKPIs(metrics) { document.getElementById('totalCorrections').textContent = metrics.total_corrections || 0; document.getElementById('avgImprovement').textContent = metrics.avg_score_improvement || 0; document.getElementById('rollbackRate').textContent = metrics.rollback_rate || 0; document.getElementById('convergenceRate').textContent = metrics.convergence_rate || 0; }
function renderHealth(health) { const badge = document.getElementById('statusBadge'); badge.textContent = (health.status || 'unknown').toUpperCase(); badge.style.background = health.status === 'healthy' ? '#3fb950' : '#f85149'; document.getElementById('uptime').textContent = 'Uptime: ' + health.uptime_seconds + 's'; }
function renderHistory(history) { const table = document.getElementById('historyTable'); table.innerHTML = ''; (history.executions || []).forEach(item => { const tr = document.createElement('tr'); const improvement = item.improvement !== undefined ? item.improvement : 0; tr.innerHTML = `<td><code>${item.id || '-'}</code></td><td>${item.timestamp || '-'}</td><td>${improvement}</td><td>${item.iterations || 0}</td><td class="${item.rollback_triggered ? 'status-bad' : 'status-ok'}">${item.rollback_triggered ? 'ROLLBACK' : 'OK'}</td>`; table.appendChild(tr); }); }
function renderBenchmark(benchmark) { const container = document.getElementById('benchmarkContent'); if (!benchmark.available) { container.innerHTML = '<div class="status-bad">No benchmark report</div>'; return; } const summary = benchmark.summary || {}; container.innerHTML = `<p><b>Pass Rate:</b> ${summary.pass_rate || 0}</p><p><b>Total Cases:</b> ${summary.total || 0}</p><p><b>Passed:</b> ${summary.passed || 0}</p><p><b>Failed:</b> ${summary.failed || 0}</p>`; }
function renderWorkspaces(workspaces) { const container = document.getElementById('workspaceList'); container.innerHTML = ''; (workspaces.workspaces || []).forEach(ws => { const div = document.createElement('div'); div.className = 'workspace'; div.innerHTML = `<div><b>${ws.name}</b></div><div>Health: ${ws.health_score}</div><div>Size: ${ws.size_mb} MB</div><div>Backups: ${ws.backups_count}</div>`; container.appendChild(div); }); }
function updateCountdown() { document.getElementById('countdown').textContent = countdown; }
async function refresh() { try { const data = await fetchData(); renderHealth(data.health); renderKPIs(data.metrics); renderHistory(data.history); renderBenchmark(data.benchmark); renderWorkspaces(data.workspaces); fetch('/jobs/metrics').then(r => r.json()).then(data => { if (!data.success) { return; } const m = data.metrics; document.getElementById('queue-size').textContent = m.queue.size; document.getElementById('queue-processed').textContent = m.throughput.jobs_processed; document.getElementById('queue-avg-duration').textContent = m.latency.avg_duration_ms + 'ms'; }); fetch('/jobs?limit=5').then(r => r.json()).then(data => { if (!data.success || !data.jobs) { return; } const tbody = document.getElementById('jobs-tbody'); tbody.innerHTML = ''; data.jobs.forEach(job => { const statusColor = { completed: '#3fb950', running: '#d2991d', pending: '#8b949e', failed: '#f85149' }[job.status] || '#8b949e'; const score = job.result ? (job.result.initial_score + ' → ' + job.result.final_score) : '-'; const row = `<tr style="background:#0d1117;"><td style="padding:8px;border:1px solid #30363d;font-family:monospace;">${job.job_id}</td><td style="padding:8px;border:1px solid #30363d;color:${statusColor};">${job.status}</td><td style="padding:8px;border:1px solid #30363d;">${score}</td><td style="padding:8px;border:1px solid #30363d;">${job.duration_ms ? (job.duration_ms + 'ms') : '-'}</td></tr>`; tbody.innerHTML += row; }); }); } catch (err) { console.error(err); } }
refresh();
setInterval(() => { countdown--; if (countdown <= 0) { refresh(); countdown = 5; } updateCountdown(); }, 1000);
</script>
</body>
</html>
"""

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        if self._auth_required(
            "GET",
            self.path,
        ):
            if not self._check_auth():
                self._send_unauthorized()
                return

        if self.path == "/health":
            METRICS["total_health_checks"] += 1
            self._send_json({
                "service": "MILODO API",
                "version": "1.0.0",
                "status": "healthy",
                "uptime_seconds": round(time.time() - SERVER_START_TIME, 1),
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
                "pid": os.getpid(),
                "workspaces_root": str(Path(".milodo/workspaces").resolve()),
                "core_modules": _check_core_modules(),
            })
            return

        if self.path.startswith("/history"):
            limit = 20

            if "?limit=" in self.path:
                try:
                    limit = int(
                        self.path.split("?limit=")[1]
                        .split("&")[0]
                    )
                    limit = min(limit, MAX_HISTORY)
                except (ValueError, IndexError):
                    limit = 20

            self._send_json({
                "service": "MILODO API",
                "total_stored": len(HISTORY),
                "max_history": MAX_HISTORY,
                "executions": HISTORY[:limit],
            })

            return

        if self.path == "/benchmark":
            self._send_json(_get_benchmark_report())
            return

        if self.path == "/metrics":
            self._send_json(_get_metrics())
            return

        if self.path.startswith("/workspaces"):
            name_filter = None

            if "?name=" in self.path:
                name_filter = (
                    self.path.split("?name=")[1]
                    .split("&")[0]
                )

            self._send_json(
                _get_workspaces(name_filter=name_filter)
            )

            return

        if self.path == "/jobs/metrics":

            self._send_json(
                {
                    "success": True,
                    "metrics": (
                        get_queue_metrics()
                    ),
                }
            )

            return

        if self.path.startswith("/jobs/"):
            job_id = (
                self.path.split("/jobs/")[1]
                .split("?")[0]
                .strip()
            )

            job = get_job_status(job_id)

            if not job:
                self._send_json(
                    {
                        "success": False,
                        "error": "Job not found",
                    },
                    status=404,
                )
                return

            self._send_json(
                {
                    "success": True,
                    "job": job,
                }
            )
            return

        if self.path.startswith("/jobs"):
            limit = 20

            if "?limit=" in self.path:
                try:
                    limit = int(
                        self.path.split("?limit=")[1]
                        .split("&")[0]
                    )
                except (ValueError, IndexError):
                    limit = 20

            self._send_json(
                {
                    "success": True,
                    "worker": get_worker_status(),
                    "jobs": get_all_jobs(limit),
                    "total": len(get_all_jobs(100)),
                    "queue_size": (
                        get_worker_status()[
                            "queue_size"
                        ]
                    ),
                }
            )
            return

        if self.path == "/dashboard":
            self._serve_dashboard()
            return

        if self.path == "/":
            self._send_json({
                "service": "MILODO API",
                "version": "1.0.0",
                "status": "running",
                "endpoints": {
                    "GET /": "Service info",
                    "POST /autocorrect": "Run autonomous HTML correction loop",
                },
            })
            return

        self._send_json(
            {
                "success": False,
                "error": "Not found",
            },
            status=404,
        )

    def do_POST(self):
        global REQUEST_COUNTER

        if self._auth_required(
            "POST",
            self.path,
        ):
            if not self._check_auth():
                self._send_unauthorized()
                return

        if self.path == "/benchmark/run":
            METRICS["total_benchmark_runs"] += 1
            self._send_json(_run_benchmark())
            return

        if self.path == "/jobs/autocorrect":
            try:
                body = self._read_body()
                html = body.get("html", "")
                max_iterations = body.get("max_iterations", 5)
                convergence_threshold = body.get(
                    "convergence_threshold",
                    0.5,
                )

                if not html:
                    self._send_json(
                        {
                            "success": False,
                            "error": "Missing 'html' field in request body",
                        },
                        status=400,
                    )
                    return

                job_id = enqueue_job(
                    html=html,
                    max_iterations=max_iterations,
                    convergence_threshold=(
                        convergence_threshold
                    ),
                )

                self._send_json(
                    {
                        "success": True,
                        "message": "Job accepted",
                        "job_id": job_id,
                        "status_url": f"/jobs/{job_id}",
                        "queue_size": (
                            get_worker_status()[
                                "queue_size"
                            ]
                        ),
                    },
                    status=202,
                )
            except Exception as error:
                self._send_json(
                    {
                        "success": False,
                        "error": str(error),
                    },
                    status=500,
                )
            return

        if self.path != "/autocorrect":
            self._send_json(
                {
                    "success": False,
                    "error": "Not found",
                },
                status=404,
            )
            return

        print("[MILODO API] POST /autocorrect — processing")
        start_time = time.time()

        try:
            body = self._read_body()
            html = body.get("html", "")
            max_iterations = body.get("max_iterations", 5)
            convergence_threshold = body.get("convergence_threshold", 0.5)

            if not html:
                self._send_json(
                    {
                        "success": False,
                        "error": "Missing 'html' field in request body",
                    },
                    status=400,
                )
                return

            result = run_autonomous_loop(
                html,
                max_iterations=max_iterations,
                convergence_threshold=convergence_threshold,
                verbose=False,
            )

            METRICS["total_requests"] += 1

            if result.get("final_score") is not None:
                METRICS["total_corrections"] += 1

                METRICS["total_score_improvement"] += float(
                    result.get("improvement", 0.0)
                )

                METRICS["total_iterations_sum"] += int(
                    result.get("iterations_count", 0)
                )

                if result.get("rollback_triggered"):
                    METRICS["total_rollbacks"] += 1

            response = {
                "success": True,
                "final_score": result["final_score"],
                "initial_score": result["initial_score"],
                "improvement": result["improvement"],
                "iterations_count": result["iterations_count"],
                "converged": result["converged"],
                "rollback_triggered": result["rollback_triggered"],
                "max_iterations_reached": result["max_iterations_reached"],
                "final_html": result["final_html"],
                "iterations": result["iterations"],
            }

            REQUEST_COUNTER += 1

            execution_record = {
                "id": REQUEST_COUNTER,
                "timestamp": datetime.now().isoformat(),
                "initial_score": result.get("initial_score"),
                "final_score": result.get("final_score"),
                "improvement": result.get("improvement"),
                "iterations": result.get("iterations_count"),
                "converged": result.get("converged"),
                "rollback_triggered": result.get("rollback_triggered"),
                "html_length": len(html) if html else 0,
                "duration_ms": round((time.time() - start_time) * 1000),
            }

            HISTORY.insert(0, execution_record)

            if len(HISTORY) > MAX_HISTORY:
                HISTORY.pop()

            print(
                "[MILODO API] Loop completed — score: "
                f"{response['initial_score']} → "
                f"{response['final_score']} "
                f"(+{response['improvement']})"
            )
            self._send_json(response)
        except Exception as error:
            METRICS["total_errors"] += 1
            print(f"[MILODO API] POST /autocorrect — error: {error}")
            self._send_json(
                {
                    "success": False,
                    "error": f"Loop execution failed: {error}",
                },
                status=500,
            )


def run_server():
    start_worker()
    LOGGER.info(
        "Queue worker started"
    )
    print("Queue worker started")
    server = HTTPServer((HOST, PORT), MILODOHandler)
    print(f"[MILODO API] Server started on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
