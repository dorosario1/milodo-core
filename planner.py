from intelligence import ai_plan
from dag_engine import DAGEngine, Task
from logger import log_info, log_error, log_warn, log_debug


def _step(step_id, action, depends_on=None):
    return {
        "id": step_id,
        "action": action,
        "depends_on": list(depends_on or []),
    }


def _plan_shopify():
    return [
        _step("product", "create product"),
        _step("landing", "create landing", ["product"]),
        _step("marketing", "launch campaign", ["landing"]),
    ]


def _plan_marketing():
    return [
        _step("content", "generate content"),
        _step("campaign", "launch campaign", ["content"]),
        _step("sales", "generate sales scripts", ["campaign"]),
    ]


def _plan_web():
    return [
        _step("landing", "create landing"),
        _step("email", "create email sequence", ["landing"]),
        _step("sales", "generate sales scripts", ["email"]),
    ]


def _plan_content():
    return [
        _step("research", "analyze topic"),
        _step("draft", "write content", ["research"]),
        _step("publish", "prepare publishing assets", ["draft"]),
    ]


def _plan_general():
    return [
        _step("analyze", "analyze goal"),
        _step("execute", "execute action", ["analyze"]),
    ]


def _validate_plan(steps):
    if not steps:
        raise ValueError("Plan must contain at least one step")

    seen = set()
    all_ids = {step["id"] for step in steps}
    visiting = set()
    visited = set()
    graph = {step["id"]: step["depends_on"] for step in steps}

    for step in steps:
        step_id = step.get("id")
        if not step_id:
            raise ValueError("Step id is required")
        if step_id in seen:
            raise ValueError(f"Duplicate step id: {step_id}")
        seen.add(step_id)

        for dependency in step.get("depends_on", []):
            if dependency not in all_ids:
                raise ValueError(f"Missing dependency: {step_id} depends on {dependency}")

    def visit(step_id):
        if step_id in visited:
            return
        if step_id in visiting:
            raise ValueError(f"Circular dependency detected at step: {step_id}")

        visiting.add(step_id)
        for dependency in graph[step_id]:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step in steps:
        visit(step["id"])

    completed = set()
    for step in steps:
        for dependency in step["depends_on"]:
            if dependency not in completed:
                raise ValueError(f"Step order invalid: {step['id']} appears before {dependency}")
        completed.add(step["id"])


def _resolve_intent(goal, decision):
    normalized_goal = str(goal or "").lower()

    if "shopify" in normalized_goal or "produit" in normalized_goal or "store" in normalized_goal:
        return "shopify"
    if "marketing" in normalized_goal or "campagne" in normalized_goal or "pub" in normalized_goal:
        return "marketing"
    if "site" in normalized_goal or "web" in normalized_goal or "landing" in normalized_goal:
        return "web"
    if "blog" in normalized_goal or "article" in normalized_goal or "content" in normalized_goal:
        return "content"

    if decision.get("_engine") == "fallback":
        return "general"

    return str(decision.get("intent", "general")).lower()


def plan_goal(goal: str) -> list[dict]:
    try:
        preview = str(goal)[:80].replace("\n", " ")
        log_debug(f"Prompt planner : {preview}...")

        decision = ai_plan(goal)
        if decision.get("_engine") == "fallback":
            log_warn("Plan basique - IA limitée")
        intent = _resolve_intent(goal, decision)

        if intent == "shopify":
            steps = _plan_shopify()
        elif intent == "marketing":
            steps = _plan_marketing()
        elif intent == "web":
            steps = _plan_web()
        elif intent == "content":
            steps = _plan_content()
        else:
            steps = _plan_general()

        _validate_plan(steps)
        for step in steps:
            description = step.get("action", "")
            log_debug(f"Étape : {description}")
        log_info(f"Plan généré : {len(steps)} étapes")
        plan = steps
        preview = str(plan)[:120].replace("\n", " ")
        log_debug(f"Plan : {preview}...")
        return steps
    except Exception as error:
        log_error(f"Erreur planification : {error}")
        raise


def plan_to_actions(plan_text, goal):
    text = f"{plan_text or ''} {goal or ''}".lower()
    actions = []
    site_requested = "vitrine" in text or "site vitrine" in text or "site html" in text

    def add_action(action, params=None):
        item = {
            "action": action,
            "params": dict(params or {}),
        }

        if item not in actions:
            actions.append(item)

    if not site_requested and ("landing" in text or "accueil" in text or "homepage" in text):
        add_action("create_landing", {"type": "landing"})

    if "vitrine" in text or "site vitrine" in text or "site html" in text:
        add_action("create_site", {"type": "vitrine"})

    if "page menu" in text or "menu" in text:
        add_action("create_page", {"name": "menu"})

    if "page contact" in text or "contact" in text:
        add_action("create_page", {"name": "contact"})

    if "test" in text:
        add_action("run_tests")

    if "documentation" in text or "readme" in text:
        add_action("generate_docs")

    if "git" in text or "versionner" in text:
        add_action("git_init")

    if not actions:
        add_action("generate_code", {"prompt": goal})

    return actions


def build_dag_plan(goal):
    log_debug(f"Construction plan DAG: {goal}")

    steps = plan_goal(goal)
    plan_text = "\n".join(str(step.get("action", "")) for step in steps)
    actions = plan_to_actions(plan_text, goal)
    tasks = steps_to_tasks(steps)
    engine = DAGEngine()

    for task in tasks:
        engine.add_task(task)

    valid = engine.validate()

    return {
        "goal": goal,
        "steps": steps,
        "plan": plan_text,
        "actions": actions,
        "tasks": [
            {
                "id": task.id,
                "dependencies": task.dependencies,
                "status": task.status,
                "result": task.result,
            }
            for task in tasks
        ],
        "valid": valid,
        "status": engine.get_status(),
    }


def steps_to_tasks(steps):
    log_debug("Conversion etapes vers taches DAG")

    tasks = []

    for step in steps:
        task_id = str(step.get("id", ""))
        action_name = str(step.get("action", ""))
        dependencies = step.get("dependencies", step.get("depends_on", []))

        tasks.append(Task(
            task_id,
            _make_task_action(task_id, action_name),
            dependencies,
        ))

    log_debug(f"Taches creees: {len(tasks)}")
    return tasks


def explain_plan(goal):
    log_debug(f"Explication plan demandee: {goal}")

    steps = plan_goal(goal)
    lines = [f"Plan pour: {goal}"]

    for index, step in enumerate(steps, start=1):
        dependencies = step.get("depends_on", [])
        dependency_text = ""

        if dependencies:
            dependency_text = f" apres {', '.join(dependencies)}"

        lines.append(f"{index}. {step['action']} ({step['id']}){dependency_text}")

    return "\n".join(lines)


def _make_task_action(task_id, action_name):
    def action():
        return {
            "task_id": task_id,
            "action": action_name,
            "message": "Tache planifiee uniquement, aucune commande executee",
        }

    return action


if __name__ == "__main__":
    log_info(plan_goal("lancer business shopify"))
