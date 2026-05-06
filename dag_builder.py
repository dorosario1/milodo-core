from agent import apply_goal_actions
from dag import DAG, Task
from planner import plan_goal


def _validate_steps(steps):
    if not steps:
        raise Exception("Planner returned no steps")

    step_ids = set()
    for step in steps:
        step_id = step.get("id")
        if not step_id:
            raise Exception("Planner step missing id")
        if step_id in step_ids:
            raise Exception(f"Duplicate planner step id: {step_id}")
        step_ids.add(step_id)

    for step in steps:
        for dependency in step.get("depends_on", []):
            if dependency not in step_ids:
                raise Exception(f"Missing dependency: {step['id']} depends on {dependency}")


def _make_task(step):
    action = step["action"]
    return Task(
        id=step["id"],
        func=lambda action=action: apply_goal_actions(action),
        dependencies=step.get("depends_on", []),
    )


def build_dag_from_goal(goal: str):
    plan = plan_goal(goal)
    _validate_steps(plan)
    tasks = [_make_task(step) for step in plan]
    return DAG(tasks), plan


if __name__ == "__main__":
    dag, plan = build_dag_from_goal("lancer business shopify")
    print(plan)
    print(dag.run())
