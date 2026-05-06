import io
import json
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ai_planner import ai_plan
from milodo import run_command


MEMORY_FILE = Path("agent_memory.json")
KNOWN_STEPS = ["build", "test", "deploy"]


class OutputCapture(io.StringIO):
    def __init__(self, stream):
        super().__init__()
        self.stream = stream

    def write(self, text):
        self.stream.write(text)
        return super().write(text)

    def flush(self):
        self.stream.flush()
        return super().flush()


def generate_plan(goal):
    result = ai_plan(goal)
    if result["safe"] is False:
        return None

    command = result["command"]

    if command == "deploy":
        return ["build", "test", "deploy"]

    if command == "test":
        return ["build", "test"]

    return ["test"]


def load_memory():
    if not MEMORY_FILE.exists():
        return {"failures": []}

    try:
        memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"failures": []}

    failures = memory.get("failures", [])
    if not isinstance(failures, list):
        failures = []

    return {"failures": [failure for failure in failures if failure in KNOWN_STEPS]}


def save_memory(memory):
    MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")


def remember_failure(memory, step):
    if step in KNOWN_STEPS and step not in memory["failures"]:
        memory["failures"].append(step)
    save_memory(memory)
    print("[AGENT] memory updated")


def reset_memory():
    save_memory({"failures": []})


def detect_failed_task(output, fallback_step):
    error_match = re.search(r"\[MILODO ERROR\]\s+failed task:\s+([a-zA-Z0-9_-]+)", output)
    if error_match:
        return error_match.group(1)

    failed_match = re.search(r"\[FAILED\]\s+([a-zA-Z0-9_-]+)", output)
    if failed_match:
        return failed_match.group(1)

    return fallback_step


def normalize_result(raw_result, output, fallback_step):
    if isinstance(raw_result, dict):
        return {
            "success": bool(raw_result.get("success")),
            "failed_task": raw_result.get("failed_task"),
        }

    success = bool(raw_result)
    return {
        "success": success,
        "failed_task": None if success else detect_failed_task(output, fallback_step),
    }


def run_step(step):
    output = OutputCapture(sys.stdout)
    error_output = OutputCapture(sys.stderr)

    with redirect_stdout(output), redirect_stderr(error_output):
        raw_result = run_command(step)

    return normalize_result(raw_result, output.getvalue() + error_output.getvalue(), step)


def next_step_for_failure(failed_task):
    if failed_task == "build":
        return "build"
    if failed_task == "test":
        return "test"
    return "deploy"


def plan_from_step(plan, next_step):
    if next_step in plan:
        return plan[plan.index(next_step):]
    return [next_step]


def run_goal(goal):
    max_attempts = 3
    memory = load_memory()
    plan = generate_plan(goal)
    if plan is None:
        print("[AGENT] unsafe or unknown goal")
        return False

    active_plan = plan
    forced_step = None

    for attempt in range(max_attempts):
        print(f"[AGENT] attempt {attempt + 1}")
        ran_step = False
        attempt_failed = False

        for step in active_plan:
            if step in memory["failures"] and step != forced_step:
                print(f"[AGENT] skipping known failure: {step}")
                continue

            ran_step = True
            result = run_step(step)

            if not result["success"]:
                failed_task = result["failed_task"]
                remember_failure(memory, failed_task)
                next_step = next_step_for_failure(failed_task)
                print(f"[AGENT] perceived failure: {failed_task}")
                print(f"[AGENT] new strategy: {next_step}")
                active_plan = plan_from_step(plan, next_step)
                forced_step = next_step
                attempt_failed = True
                break

        if not attempt_failed and ran_step:
            reset_memory()
            print("[AGENT] goal achieved")
            return True

        if not ran_step:
            break

    print("[AGENT] failed after retries")
    return False
