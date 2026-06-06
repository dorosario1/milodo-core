import queue
import threading
import time
import uuid
from datetime import datetime


JOB_QUEUE = queue.Queue()

JOB_RESULTS = {}

JOB_HISTORY = {}

WORKER_STATUS = {
    "running": False,
    "jobs_processed": 0,
    "jobs_failed": 0,
    "started_at": None,
}

WORKER_THREAD = None


def _worker_loop():
    from skills.autonomous_loop import (
        run_autonomous_loop
    )

    while WORKER_STATUS["running"]:

        try:
            job_id = JOB_QUEUE.get(
                timeout=1
            )

        except queue.Empty:
            continue

        job = JOB_HISTORY.get(job_id)

        if not job:
            JOB_QUEUE.task_done()
            continue

        job["status"] = "running"

        job["started_at"] = (
            datetime.now().isoformat()
        )

        start_time = time.time()

        try:

            result = run_autonomous_loop(
                original_html=job["input"]["html"],
                max_iterations=job["input"][
                    "max_iterations"
                ],
                convergence_threshold=job[
                    "input"
                ][
                    "convergence_threshold"
                ],
                verbose=False,
            )

            job["status"] = "completed"

            job["result"] = result

            WORKER_STATUS[
                "jobs_processed"
            ] += 1

        except Exception as e:

            job["status"] = "failed"

            job["error"] = str(e)

            WORKER_STATUS[
                "jobs_failed"
            ] += 1

        finally:

            job["completed_at"] = (
                datetime.now().isoformat()
            )

            job["duration_ms"] = round(
                (time.time() - start_time)
                * 1000
            )

            JOB_RESULTS[job_id] = job

            JOB_QUEUE.task_done()


def start_worker() -> None:
    """
    Start daemon worker thread.
    """
    global WORKER_THREAD

    if (
        WORKER_THREAD is not None
        and WORKER_THREAD.is_alive()
    ):
        return

    WORKER_STATUS["running"] = True
    WORKER_STATUS["started_at"] = (
        datetime.now().isoformat()
    )
    WORKER_THREAD = threading.Thread(
        target=_worker_loop,
        daemon=True,
        name="milodo-queue-worker",
    )
    WORKER_THREAD.start()


def stop_worker() -> None:
    """
    Stop worker cleanly.
    """
    global WORKER_THREAD

    WORKER_STATUS["running"] = False

    if WORKER_THREAD is not None:
        WORKER_THREAD.join(timeout=3)

    WORKER_THREAD = None


def enqueue_job(
    html: str,
    max_iterations: int = 5,
    convergence_threshold: float = 0.5,
) -> str:
    """
    Add job to queue.
    Return short job_id.
    """
    job_id = uuid.uuid4().hex[:8]

    job = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "input": {
            "html": html,
            "html_length": len(html),
            "max_iterations": max_iterations,
            "convergence_threshold": convergence_threshold,
        },
        "result": None,
        "error": None,
    }

    JOB_HISTORY[job_id] = job

    JOB_QUEUE.put(job_id)

    return job_id


def get_job_status(
    job_id: str,
) -> dict | None:
    """
    Return job details.
    """
    return JOB_HISTORY.get(job_id)


def get_all_jobs(
    limit: int = 20,
) -> list:
    """
    Return latest jobs.
    """
    safe_limit = min(max(int(limit), 0), 100)
    return sorted(
        JOB_HISTORY.values(),
        key=lambda job: job["created_at"],
        reverse=True,
    )[:safe_limit]


def get_worker_status() -> dict:
    """
    Return worker runtime stats.
    """
    started_at = WORKER_STATUS["started_at"]
    uptime_seconds = 0.0

    if started_at:
        uptime_seconds = round(
            (
                datetime.now()
                - datetime.fromisoformat(started_at)
            ).total_seconds(),
            1,
        )

    return {
        "running": WORKER_STATUS["running"],
        "jobs_processed": WORKER_STATUS["jobs_processed"],
        "jobs_failed": WORKER_STATUS["jobs_failed"],
        "queue_size": JOB_QUEUE.qsize(),
        "started_at": started_at,
        "uptime_seconds": uptime_seconds,
    }


def get_queue_metrics() -> dict:
    """
    Return real-time queue metrics.
    """

    now = datetime.now()

    completed_jobs = [
        j
        for j in JOB_HISTORY.values()
        if (
            j.get("status") == "completed"
            and j.get("duration_ms")
        )
    ]

    avg_duration_ms = (
        round(
            sum(
                j["duration_ms"]
                for j in completed_jobs
            )
            / len(completed_jobs)
        )
        if completed_jobs
        else 0
    )

    recent_jobs = [
        j
        for j in JOB_HISTORY.values()
        if (
            j.get("completed_at")
            and (
                now
                - datetime.fromisoformat(
                    j["completed_at"]
                )
            ).total_seconds()
            < 300
            and j.get("status")
            == "completed"
        )
    ]

    throughput_per_min = (
        round(len(recent_jobs) / 5, 1)
        if recent_jobs
        else 0
    )

    total_processed = (
        WORKER_STATUS["jobs_processed"]
    )

    total_failed = (
        WORKER_STATUS["jobs_failed"]
    )

    total_all = (
        total_processed
        + total_failed
    )

    success_rate = (
        round(
            (
                total_processed
                / total_all
            )
            * 100,
            1,
        )
        if total_all > 0
        else 100.0
    )

    uptime_seconds = 0

    if WORKER_STATUS["started_at"]:

        uptime_seconds = round(
            (
                now
                - datetime.fromisoformat(
                    WORKER_STATUS[
                        "started_at"
                    ]
                )
            ).total_seconds()
        )

    return {
        "worker": {
            "running": WORKER_STATUS[
                "running"
            ],
            "started_at": WORKER_STATUS[
                "started_at"
            ],
            "uptime_seconds": uptime_seconds,
        },
        "queue": {
            "size": JOB_QUEUE.qsize(),
            "max_size": 0,
        },
        "throughput": {
            "jobs_processed": total_processed,
            "jobs_failed": total_failed,
            "per_minute": throughput_per_min,
            "success_rate": success_rate,
        },
        "latency": {
            "avg_duration_ms": avg_duration_ms,
            "total_jobs_completed": len(
                completed_jobs
            ),
        },
    }


def cleanup_old_jobs(
    max_age_seconds: int = 3600,
) -> int:
    """
    Cleanup completed old jobs.
    """
    now = datetime.now()
    removed = 0

    for job_id, job in list(JOB_HISTORY.items()):
        if job["status"] not in ("completed", "failed"):
            continue

        completed_at = job.get("completed_at")
        if not completed_at:
            continue

        age = (
            now - datetime.fromisoformat(completed_at)
        ).total_seconds()

        if age > max_age_seconds:
            JOB_HISTORY.pop(job_id, None)
            JOB_RESULTS.pop(job_id, None)
            removed += 1

    return removed
