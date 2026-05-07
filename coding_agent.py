from pathlib import Path

import intelligence
from file_tools import read_file, write_file, exists
from logger import log_info, log_error, log_warn, log_debug
from state_recall import get_last_project


def generate_code(prompt):
    preview = str(prompt)[:80].replace("\n", " ")
    log_debug(f"Prompt génération : {preview}...")

    full_prompt = _build_prompt(
        "Genere uniquement le code demande, sans explication inutile.",
        prompt,
    )

    result = _ask_intelligence(full_prompt)

    if not result:
        log_warn("Fallback coding - IA indisponible")
        return ""

    code = _clean_code_result(result)
    log_info("Code généré via IA")
    log_debug(f"Code généré : {len(code)} caractères")
    return code


def create_file(path, prompt):
    file_path = Path(path)
    log_debug(f"Creation fichier demandee: {file_path}")

    content = generate_code(prompt)

    if not content:
        raise RuntimeError("Creation annulee: aucun contenu genere")

    write_file(file_path, content)
    log_info(f"Fichier créé : {file_path}")
    return content


def modify_file(path, instruction):
    file_path = Path(path)
    log_debug(f"Modification fichier demandee: {file_path}")

    _ensure_file_exists(file_path)
    original_content = read_file(file_path)

    prompt = _build_prompt(
        "Modifie le fichier selon l'instruction. Retourne uniquement le contenu complet du fichier modifie.",
        f"Instruction:\n{instruction}\n\nContenu actuel:\n{original_content}",
    )

    updated_content = _ask_intelligence(prompt)

    if not updated_content:
        log_warn("Fallback coding - IA indisponible")
        return original_content

    updated_content = _clean_code_result(updated_content)
    write_file(file_path, updated_content)
    log_info(f"Fichier modifié : {file_path}")
    return updated_content


def fix_file(path):
    file_path = Path(path)
    log_debug(f"Correction fichier demandee: {file_path}")

    _ensure_file_exists(file_path)
    original_content = read_file(file_path)

    prompt = _build_prompt(
        "Corrige les erreurs du fichier. Retourne uniquement le contenu complet corrige.",
        f"Contenu actuel:\n{original_content}",
    )

    fixed_content = _ask_intelligence(prompt)

    if not fixed_content:
        log_warn("Fallback coding - IA indisponible")
        return original_content

    fixed_content = _clean_code_result(fixed_content)
    write_file(file_path, fixed_content)
    log_info(f"Fichier modifié : {file_path}")
    return fixed_content


def explain_file(path):
    file_path = Path(path)
    log_debug(f"Explication fichier demandee: {file_path}")

    _ensure_file_exists(file_path)
    content = read_file(file_path)

    prompt = _build_prompt(
        "Explique clairement et simplement ce fichier.",
        f"Chemin: {file_path}\n\nContenu:\n{content}",
    )

    explanation = _ask_intelligence(prompt)

    if not explanation:
        log_warn("Fallback coding - IA indisponible")
        return "Explication indisponible: IA indisponible."

    log_info(f"Explication generee: {file_path}")
    return explanation.strip()


def _ask_intelligence(prompt):
    try:
        preview = str(prompt)[:80].replace("\n", " ")
        log_debug(f"Prompt génération : {preview}...")
        hybrid = intelligence.hybrid

        result = hybrid.ask_ollama(prompt)
        if result:
            return result

        result = hybrid.ask_openai(prompt)
        if result:
            return result

        return None
    except Exception as error:
        log_error(f"Erreur génération : {error}")
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


def _clean_code_result(content):
    text = content.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return text


def _ensure_file_exists(path):
    file_path = Path(path)

    if not exists(file_path):
        log_warn(f"Fichier introuvable: {file_path}")
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")

    if not file_path.is_file():
        log_warn(f"Chemin invalide, fichier attendu: {file_path}")
        raise IsADirectoryError(f"Chemin invalide, fichier attendu: {file_path}")
