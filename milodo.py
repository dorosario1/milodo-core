import argparse
import sys
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
from chat_server import start_server
from dag_engine import DAGEngine
from dag_builder import build_dag_from_goal
from intelligence import ai_plan
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
    print(f"[MILODO] Run DAG: {goal}")
    dag_plan = build_dag_plan(goal)
    tasks = steps_to_tasks(dag_plan["steps"])
    engine = DAGEngine()

    for task in tasks:
        engine.add_task(task)

    result = engine.run()

    print({
        "success": result.get("success", False),
        "goal": goal,
        "plan": dag_plan,
        "result": result,
    })
    return 0 if result.get("success", False) else 1


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
