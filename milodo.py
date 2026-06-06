import argparse
import json
import sys

if len(sys.argv) > 1 and sys.argv[1] == "inspect-memory":
    from core import causal_inspector_cli

    sys.argv = [sys.argv[0], *sys.argv[2:]]
    sys.exit(causal_inspector_cli.main())

import time
import webbrowser
from pathlib import Path

import architect_agent
import coding_agent
import executor
import memory
import project_scanner
import shopify_manager
import skill_loader
import state_recall
import workspace_manager
import workspace_sandbox
from action_executor import execute_actions
from chat_server import start_server
from dag_engine import DAGEngine
from dag_builder import build_dag_from_goal
from intelligence import ai_plan
from logger import log_warn
from planner import build_dag_plan, explain_plan, plan_goal, steps_to_tasks
from state_store import init_db, save_run, save_task


def print_usage():
    print('Usage: milodo run "your goal"')


def print_plan(plan):
    print("[MILODO] Plan:")
    for step in plan:
        print(f" - {step['id']} ({step['action']})")


def run_command(goal: str):
    goal = str(goal or "").strip()
    if not goal:
        print("[MILODO] Error: empty goal")
        return False

    try:
        init_db()
    except Exception as error:
        print(f"[MILODO] DB Error: {error}")

    try:
        print(f"[MILODO] Goal: {goal}")
        decision = ai_plan(goal)
        print(f"[MILODO] Decision: {decision}")
        dag, plan = build_dag_from_goal(goal)
        print_plan(plan)
    except Exception as error:
        print(f"[MILODO] Error: planner failed: {error}")
        return False

    try:
        result = dag.run()
    except Exception as error:
        print(f"[MILODO] Error: DAG failed: {error}")
        return False

    success = bool(result.get("success"))
    if not success:
        print("[MILODO] Error: DAG execution failed")

    try:
        run_id = save_run(goal, decision, success)
        for task in dag.tasks.values():
            save_task(run_id, task)
    except Exception as error:
        print(f"[MILODO] DB Error: {error}")

    print()
    print("[MILODO] RESULT:")
    print(result)
    return success


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    if not args.command:
        print_usage()
        parser.print_help()
        return 1

    try:
        if args.command == "scan":
            return command_scan()

        if args.command == "status":
            return command_status()

        if args.command == "plan":
            return command_plan(args.goal)

        if args.command == "run":
            return command_run(args.goal)

        if args.command == "approve":
            return command_approve()

        if args.command == "remember":
            return command_remember(args.entry_type, args.content)

        if args.command == "memory":
            return command_memory(args.query)

        if args.command == "skills":
            return command_skills()

        if args.command == "chat":
            return command_chat()

        print("[MILODO] Error: unknown command")
        return 1
    except Exception as error:
        print(f"[MILODO] Error: {error}")
        return 1


def build_parser():
    parser = argparse.ArgumentParser(description="MILODO CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("scan", help="Scanner projets")
    subparsers.add_parser("status", help="Afficher etat projets + memoire")

    plan_parser = subparsers.add_parser("plan", help="Generer plan MILODO")
    plan_parser.add_argument("goal", help="Objectif utilisateur")

    run_parser = subparsers.add_parser("run", help="Executer DAG planifie sans commande systeme")
    run_parser.add_argument("goal", help="Objectif utilisateur")

    subparsers.add_parser("approve", help="Approuver le workspace en attente")

    remember_parser = subparsers.add_parser("remember", help="Ajouter memoire")
    remember_parser.add_argument("entry_type", help="Type entree memoire")
    remember_parser.add_argument("content", help="Contenu memoire")

    memory_parser = subparsers.add_parser("memory", help="Rechercher memoire")
    memory_parser.add_argument("query", help="Recherche texte")

    subparsers.add_parser("skills", help="Afficher skills dynamiques")
    subparsers.add_parser("chat", help="Demarrer chat local MILODO")

    return parser


def command_scan():
    print("[MILODO] Scan projets")
    projects = project_scanner.scan_projects()
    project_scanner.save_projects(projects)
    print({
        "success": True,
        "projects_count": len(projects),
        "projects": projects,
    })
    return 0


def command_status():
    print("[MILODO] Status")
    projects = state_recall.load_projects()
    state = state_recall.load_state()
    entries = memory.get_memory_entries()

    result = {
        "success": True,
        "projects_count": len(projects),
        "last_project": state.get("last_project", {}),
        "memory_entries_count": len(entries),
        "integrations": {
            "project_scanner": bool(project_scanner),
            "state_recall": bool(state_recall),
            "planner": bool(plan_goal),
            "dag_engine": bool(DAGEngine),
            "coding_agent": bool(coding_agent),
            "architect_agent": bool(architect_agent),
            "executor": bool(executor),
            "memory": bool(memory),
            "shopify_manager": bool(shopify_manager),
        },
    }

    print(result)
    return 0


def command_plan(goal):
    print(f"[MILODO] Plan: {goal}")
    steps = plan_goal(goal)
    explanation = explain_plan(goal)

    print({
        "success": True,
        "goal": goal,
        "steps": steps,
        "explanation": explanation,
    })
    return 0


def command_run(goal):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"[MILODO] Run DAG: {goal}")
    dag_plan = build_dag_plan(goal)
    actions = dag_plan.get("actions", [])
    output_dir = Path(__file__).resolve().parent / "business_outputs"
    sandbox_context = {"workspace_path": str(output_dir)}
    try:
        workspace_result = workspace_manager.prepare_run_context(goal)
        if workspace_result.get("success") and workspace_result.get("workspace"):
            sandbox_result = workspace_sandbox.create_workspace(
                workspace_result["workspace"]
            )
            sandbox_context = workspace_sandbox.build_run_context(
                sandbox_result["workspace_dir"]
            )
            sandbox_output_dir = sandbox_context.get("output_dir")
            if sandbox_output_dir:
                output_dir = Path(sandbox_output_dir)
    except Exception as error:
        log_warn(f"Workspace sandbox indisponible, fallback business_outputs : {error}")
    project_name = str(goal).replace("site vitrine restaurant", "").replace("avec menu et contact", "").strip() or "milodo_project"

    for item in actions:
        action_name = item.get("action")
        params = item.setdefault("params", {})

        if action_name in {"create_landing", "create_site", "generate_site"}:
            params.setdefault("name", project_name)

        if action_name == "create_page":
            page_name = params.get("name", "page")
            params.setdefault("content", f"<h1>{page_name.title()}</h1>\n<p>{goal}</p>\n")

    tasks = steps_to_tasks(dag_plan["steps"])
    engine = DAGEngine()

    for task in tasks:
        engine.add_task(task)

    workspace_before = _snapshot_workspace(sandbox_context["workspace_path"])
    result = engine.run()
    action_result = execute_actions(actions, output_dir)
    workspace_after = _snapshot_workspace(sandbox_context["workspace_path"])
    workspace_changes = _diff_workspace_snapshots(workspace_before, workspace_after)
    run_success = result.get("success", False) and action_result.get("success", False)
    workspace_report = {
        "project": project_name,
        "workspace": sandbox_context["workspace_path"],
        "actions": [
            item.get("action")
            for item in action_result.get("results", [])
        ],
        "files_created": action_result.get("files_created", []),
        "workspace_changes": workspace_changes,
        "success": run_success,
    }
    pending_approval = None

    if run_success:
        pending_approval = _save_pending_workspace_approval(workspace_report)

    print(f"✅ {action_result.get('completed', 0)}/{action_result.get('total', 0)} actions réussies")
    print(f"Projet créé dans : {output_dir}")

    if action_result.get("failed", 0):
        print("❌ Erreurs éventuelles")
        for item in action_result.get("results", []):
            if not item.get("success"):
                print(f" - {item.get('action')}: {item.get('error')}")

    print({
        "success": run_success,
        "goal": goal,
        "plan": dag_plan,
        "result": result,
        "actions": action_result,
        "workspace_report": workspace_report,
        "pending_approval": pending_approval,
    })
    return 0 if run_success else 1


def command_remember(entry_type, content):
    print(f"[MILODO] Remember: {entry_type}")
    result = memory.add_memory_entry(entry_type, content)
    print(result)
    return 0 if result.get("success", False) else 1


def command_memory(query):
    print(f"[MILODO] Memory search: {query}")
    results = memory.search_memory(query)
    print({
        "success": True,
        "query": query,
        "results_count": len(results),
        "results": results,
    })
    return 0


def command_approve():
    approval_path = Path(".milodo") / "pending_workspace_approval.json"

    if not approval_path.exists():
        print(f"[MILODO] Error: fichier introuvable : {approval_path}")
        return 1

    with approval_path.open("r", encoding="utf-8") as file:
        pending = json.load(file)

    if not isinstance(pending, dict):
        print(f"[MILODO] Error: JSON invalide : {approval_path}")
        return 1

    fields = ["project", "workspace", "added", "modified", "deleted", "status"]

    print("[MILODO] Approval before:")
    for field in fields:
        print(f"{field}: {pending.get(field)}")

    pending["status"] = "approved"

    tmp_path = approval_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(pending, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(approval_path)

    print("[MILODO] Approval after:")
    for field in fields:
        print(f"{field}: {pending.get(field)}")

    print("[MILODO] Success: workspace approved")
    return 0


def _snapshot_workspace(workspace_path):
    root = Path(workspace_path)
    snapshot = {}

    if not root.exists():
        return snapshot

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        try:
            stat = path.stat()
            relative_path = path.relative_to(root).as_posix()
            snapshot[relative_path] = {
                "path": relative_path,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        except OSError:
            continue

    return snapshot


def _diff_workspace_snapshots(before, after):
    before_paths = set(before)
    after_paths = set(after)

    added = sorted(after_paths - before_paths)
    deleted = sorted(before_paths - after_paths)
    modified = sorted(
        path
        for path in before_paths & after_paths
        if (
            before[path].get("size") != after[path].get("size")
            or before[path].get("mtime_ns") != after[path].get("mtime_ns")
        )
    )

    return {
        "added": added,
        "modified": modified,
        "deleted": deleted,
    }


def _save_pending_workspace_approval(workspace_report):
    workspace_changes = workspace_report.get("workspace_changes", {})
    pending = {
        "project": workspace_report.get("project", ""),
        "workspace": workspace_report.get("workspace", ""),
        "added": len(workspace_changes.get("added", [])),
        "modified": len(workspace_changes.get("modified", [])),
        "deleted": len(workspace_changes.get("deleted", [])),
        "status": "pending_approval",
    }
    approval_path = Path(".milodo") / "pending_workspace_approval.json"
    approval_path.parent.mkdir(exist_ok=True)
    tmp_path = approval_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(pending, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(approval_path)
    return {
        "path": str(approval_path),
        "content": pending,
    }


def command_skills():
    print("[MILODO] Skills")
    result = skill_loader.load_all_skills()
    print(result)
    return 0


def command_chat():
    start_server()
    chat_path = Path(__file__).resolve().parent / "chat.html"
    webbrowser.open(chat_path.as_uri())
    print(" Chat MILODO demarre sur http://127.0.0.1:8520")
    print("Ctrl+C pour arreter")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Chat MILODO arrete")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
