from pathlib import Path

import intelligence
from logger import log_info, log_error, log_warn, log_debug
from state_recall import get_last_project, load_projects


def design_architecture(prompt):
    preview = str(prompt)[:80].replace("\n", " ")
    log_debug(f"Prompt architecture : {preview}...")

    full_prompt = _build_prompt(
        "Propose une architecture technique simple, stable et realiste. Retourne uniquement un plan textuel.",
        prompt,
    )

    result = _ask_intelligence(full_prompt)

    if not result:
        log_warn("Planification basique - IA limitée")
        plan = _fallback_architecture(prompt)
        preview = str(plan)[:120].replace("\n", " ")
        log_debug(f"Architecture : {preview}...")
        return plan

    plan = result.strip()
    log_info("Architecture générée : architecture")
    preview = str(plan)[:120].replace("\n", " ")
    log_debug(f"Architecture : {preview}...")
    return plan


def plan_project_structure(project_name, project_type):
    log_debug(f"Plan structure demande: {project_name} ({project_type})")

    prompt = (
        f"Projet: {project_name}\n"
        f"Type: {project_type}\n"
        "Propose une structure de dossiers et fichiers minimale."
    )

    result = _ask_intelligence(_build_prompt(
        "Propose uniquement une arborescence et une courte description des fichiers.",
        prompt,
    ))

    if not result:
        log_warn("Planification basique - IA limitée")
        plan = _fallback_structure(project_name, project_type)
        preview = str(plan)[:120].replace("\n", " ")
        log_debug(f"Architecture : {preview}...")
        return plan

    plan = result.strip()
    log_info(f"Architecture générée : {project_name}")
    preview = str(plan)[:120].replace("\n", " ")
    log_debug(f"Architecture : {preview}...")
    return plan


def generate_technical_roadmap(project_goal):
    log_debug("Roadmap technique demandee")

    prompt = _build_prompt(
        "Genere une roadmap technique simple en phases courtes et actionnables.",
        project_goal,
    )

    result = _ask_intelligence(prompt)

    if not result:
        log_warn("Planification basique - IA limitée")
        plan = _fallback_roadmap(project_goal)
        preview = str(plan)[:120].replace("\n", " ")
        log_debug(f"Architecture : {preview}...")
        return plan

    plan = result.strip()
    log_info("Architecture générée : roadmap")
    preview = str(plan)[:120].replace("\n", " ")
    log_debug(f"Architecture : {preview}...")
    return plan


def review_architecture(path):
    project_path = Path(path)
    log_debug(f"Analyse architecture demandee: {project_path}")

    last_project = get_last_project()
    known_projects = load_projects()

    prompt = (
        f"Chemin a analyser: {project_path}\n"
        f"Projet courant: {last_project}\n"
        f"Projets connus: {known_projects}\n\n"
        "Analyse l'architecture probable du projet a partir de ce contexte. "
        "Retourne points forts, risques et prochaines actions simples."
    )

    result = _ask_intelligence(_build_prompt(
        "Produis une analyse architecture courte et utile. Ne propose aucune modification automatique.",
        prompt,
    ))

    if not result:
        log_warn("Planification basique - IA limitée")
        plan = _fallback_review(project_path, last_project)
        preview = str(plan)[:120].replace("\n", " ")
        log_debug(f"Architecture : {preview}...")
        return plan

    plan = result.strip()
    log_info(f"Architecture générée : {project_path.name}")
    preview = str(plan)[:120].replace("\n", " ")
    log_debug(f"Architecture : {preview}...")
    return plan


def _ask_intelligence(prompt):
    try:
        preview = str(prompt)[:80].replace("\n", " ")
        log_debug(f"Prompt architecture : {preview}...")
        hybrid = intelligence.hybrid

        result = hybrid.ask_ollama(prompt)
        if result:
            return result

        result = hybrid.ask_openai(prompt)
        if result:
            return result

        return None
    except Exception as error:
        log_error(f"Erreur planification : {error}")
        return None


def _build_prompt(system_instruction, user_prompt):
    last_project = get_last_project()
    project_context = ""

    if last_project:
        project_context = (
            f"Projet courant: {last_project.get('name', '')}\n"
            f"Chemin projet: {last_project.get('path', '')}\n"
            f"Types projet: {last_project.get('types', [])}\n\n"
        )

    return (
        f"{system_instruction}\n\n"
        f"{project_context}"
        f"Demande:\n{user_prompt}"
    )


def _fallback_architecture(prompt):
    return (
        "Architecture technique proposee:\n"
        "- Identifier le type principal du projet.\n"
        "- Separer configuration, logique metier, interface et tests.\n"
        "- Garder une structure minimale et lisible.\n"
        "- Ajouter les fichiers uniquement quand ils deviennent necessaires.\n\n"
        f"Objectif: {prompt}"
    )


def _fallback_structure(project_name, project_type):
    return (
        f"Structure proposee pour {project_name} ({project_type}):\n"
        "- README.md\n"
        "- src/\n"
        "- tests/\n"
        "- config/\n"
        "- .env.example\n\n"
        "Cette structure est indicative et aucun fichier n'a ete cree."
    )


def _fallback_roadmap(project_goal):
    return (
        "Roadmap technique:\n"
        "1. Clarifier le besoin et les entrees/sorties.\n"
        "2. Definir la structure minimale du projet.\n"
        "3. Implementer le coeur fonctionnel.\n"
        "4. Ajouter les tests essentiels.\n"
        "5. Verifier execution locale et logs.\n\n"
        f"Objectif: {project_goal}"
    )


def _fallback_review(path, last_project):
    return (
        f"Analyse architecture pour: {path}\n"
        f"Projet courant: {last_project or 'non defini'}\n\n"
        "- Contexte limite: IA indisponible.\n"
        "- Verifier les fichiers de configuration principaux.\n"
        "- Identifier les dossiers source, tests et build.\n"
        "- Garder les changements futurs petits et controles."
    )
