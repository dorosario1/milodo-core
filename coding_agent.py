import difflib
from pathlib import Path

import intelligence
from file_tools import read_file, write_file, exists
from logger import log_info, log_error, log_warn, log_debug
from state_recall import get_last_project


TEMPLATES = {
    "restaurant": {
        "description": "Site vitrine pour restaurant",
        "files": [
            {"name": "index.html", "description": "Accueil - hero, présentation, plats vedettes, témoignages"},
            {"name": "menu.html", "description": "Menu complet - entrées, plats, desserts, boissons avec prix"},
            {"name": "contact.html", "description": "Contact - formulaire, adresse, horaires, carte"}
        ]
    },

    "portfolio": {
        "description": "Portfolio personnel ou professionnel",
        "files": [
            {"name": "index.html", "description": "Accueil - hero, présentation, compétences"},
            {"name": "projects.html", "description": "Projets - galerie avec descriptions"},
            {"name": "contact.html", "description": "Contact - formulaire, réseaux sociaux"}
        ]
    },

    "landing": {
        "description": "Landing page produit ou service",
        "files": [
            {"name": "index.html", "description": "Landing - hero, features, pricing, CTA"}
        ]
    },

    "shop": {
        "description": "Boutique e-commerce simple",
        "files": [
            {"name": "index.html", "description": "Accueil boutique - produits vedettes"},
            {"name": "products.html", "description": "Catalogue produits - grille avec prix"},
            {"name": "cart.html", "description": "Panier - liste articles, total"},
            {"name": "contact.html", "description": "Contact - formulaire, SAV"}
        ]
    }
}


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


def generate_code_stream(prompt):
    """
    Génère du code via Ollama avec streaming en direct.
    Affiche chaque token dans la console au fur et à mesure.
    Retourne le code complet à la fin.
    """

    try:
        import json
        import requests

        url = intelligence.hybrid.config.get(
            "ollama",
            {}
        ).get(
            "url",
            "http://localhost:11434"
        )

        model = intelligence.hybrid.config.get(
            "ollama",
            {}
        ).get(
            "model",
            "llama3.2"
        )

        response = requests.post(
            f"{url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True
            },
            stream=True,
            timeout=300
        )

        full_code = ""

        for line in response.iter_lines():
            if not line:
                continue

            try:
                data = json.loads(line.decode("utf-8"))

                token = data.get("response", "")

                if token:
                    print(token, end="", flush=True)
                    full_code += token

            except Exception:
                continue

        print()

        return full_code

    except Exception as e:
        log_error(f"Streaming Ollama error: {e}")
        return None


def clean_llm_output(content):
    """
    Nettoie la sortie brute d'un LLM pour ne garder que le code.
    """

    if not content:
        return ""

    import re

    cleaned = str(content).strip()

    # Supprimer les blocs markdown
    cleaned = re.sub(
        r"```(?:html|css|js|javascript)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = cleaned.replace("```", "")

    # Supprimer les phrases parasites
    parasites = [
        "Voici le code",
        "Voici la page",
        "Voici le HTML",
        "Voici un exemple",
        "J'espère que cela aide",
        "J'espère que ça aide"
    ]

    for p in parasites:
        cleaned = cleaned.replace(p, "")

    # Garder uniquement à partir du vrai HTML
    doctype_index = cleaned.find("<!DOCTYPE")
    html_index = cleaned.find("<html")

    start = -1

    if doctype_index != -1:
        start = doctype_index
    elif html_index != -1:
        start = html_index

    if start != -1:
        cleaned = cleaned[start:]

    # Couper après </html>
    end_html = cleaned.rfind("</html>")

    if end_html != -1:
        cleaned = cleaned[:end_html + len("</html>")]

    return cleaned.strip()


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
    """
    Lit un fichier, détecte les erreurs, les corrige via Ollama.
    """

    try:
        code = read_file(path)

        if not code:
            return {
                "success": False,
                "path": path,
                "changes": "Fichier vide ou introuvable"
            }

        prompt = f"""
Corrige les erreurs HTML/CSS/JS dans ce code.

OBJECTIFS :
- Corriger les erreurs de syntaxe
- Corriger les balises invalides
- Corriger le CSS cassé
- Corriger le JavaScript invalide
- Garder la structure existante
- Retourner UNIQUEMENT le code corrigé complet

CODE :
{code}
"""

        corrected_code = intelligence.hybrid.ask_ollama(prompt)

        if not corrected_code:
            return {
                "success": False,
                "path": path,
                "changes": "Aucune correction générée"
            }

        corrected_code = clean_llm_output(corrected_code)

        write_file(path, corrected_code)

        return {
            "success": True,
            "path": path,
            "changes": "Code corrigé et réécrit"
        }

    except Exception as e:
        return {
            "success": False,
            "path": path,
            "changes": str(e)
        }


def generate_multi_files(prompt, output_dir, files_spec):
    """
    Génère plusieurs fichiers en un seul appel LLM.

    prompt : description du projet
    output_dir : dossier de sortie
    files_spec : liste de {"name": "index.html", "description": "page d'accueil"}

    Retourne {"success": True/False, "files_created": [...], "errors": [...]}
    """

    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        files_created = []
        errors = []

        for file in files_spec:
            try:
                filename = file.get("name", "index.html")
                description = file.get("description", "")

                single_prompt = f"""
Projet : {prompt}

Génère UNIQUEMENT le code HTML complet pour :

{description}

Nom du fichier :
{filename}

RÈGLES ABSOLUES :
- HTML5 valide
- Responsive
- UTF-8
- Contenu réaliste
- Pas de markdown
- Pas d'explications
- Retourner UNIQUEMENT le code HTML
"""

                generated = generate_code(single_prompt)

                if not generated:
                    errors.append(f"Aucun contenu généré : {filename}")
                    continue

                generated = clean_llm_output(generated)

                file_path = output_path / filename

                write_file(file_path, generated)

                files_created.append(str(file_path))

            except Exception as file_error:
                errors.append(f"{filename}: {file_error}")
                continue

        return {
            "success": len(files_created) > 0,
            "files_created": files_created,
            "errors": errors
        }

    except Exception as e:
        return {
            "success": False,
            "files_created": [],
            "errors": [str(e)]
        }


def generate_from_template(template_type, project_name, output_dir):
    """
    Génère un projet complet à partir d'un template prédéfini.

    template_type : "restaurant" | "portfolio" | "landing" | "shop"
    project_name : nom du projet
    output_dir : dossier de sortie

    Retourne {"success": True/False, "files_created": [...], "output_dir": "..."}
    """

    if template_type not in TEMPLATES:
        return {
            "success": False,
            "files_created": [],
            "output_dir": output_dir,
            "errors": [f"Template inconnu : {template_type}"]
        }

    template = TEMPLATES[template_type]

    prompt = f"""
Projet : {project_name}

Type :
{template['description']}

Génère un projet complet moderne, responsive et professionnel.
Le contenu doit être réaliste, détaillé et en français.
"""

    result = generate_multi_files(
        prompt=prompt,
        output_dir=output_dir,
        files_spec=template["files"]
    )

    result["output_dir"] = str(output_dir)

    return result


def auto_fix_loop(path, max_attempts=3):
    """
    Boucle auto-corrective : valide → corrige → revalide.

    path : chemin du fichier à vérifier/corriger
    max_attempts : nombre max de tentatives

    Retourne {"success": True/False, "attempts": n, "initial_errors": [...], "final_errors": [...]}
    """

    backup_path = None
    diff = []
    stop_reason = None

    try:
        from validate_file import validate_file
        from validate_file import quality_score

        initial = validate_file(path)

        if initial["valid"]:
            log_info(f"Fichier déjà valide : {path}")
            return {
                "success": True,
                "attempts": 0,
                "initial_errors": [],
                "final_errors": [],
                "backup_path": backup_path,
                "diff": diff,
                "diff_lines": len(diff),
                "stop_reason": stop_reason
            }

        current = initial
        before_score = quality_score(path)
        before_errors = before_score["errors"]

        backup_path = path + ".bak"

        try:
            original_content = read_file(path)

            if original_content:
                write_file(backup_path, original_content)
                log_info(f"Backup créé : {backup_path}")

        except Exception as backup_error:
            log_warn(f"Impossible de créer le backup : {backup_error}")
            backup_path = None

        before = read_file(path) or ""

        for attempt in range(1, max_attempts + 1):
            log_info(f"Tentative {attempt}/{max_attempts} : {path} ({len(current['errors'])} erreurs)")

            fix_file(path)

            after = read_file(path) or ""

            diff = list(
                difflib.unified_diff(
                    before.splitlines(keepends=True),
                    after.splitlines(keepends=True),
                    fromfile=f"{path}.bak",
                    tofile=path
                )
            )

            if not diff:
                log_warn(f"Aucun changement détecté après correction : {path}")

            before = after

            after_score = quality_score(path)
            after_errors = after_score["errors"]
            current = validate_file(path)

            # ====================================
            # ARRÊT ANTICIPÉ — AUCUN CHANGEMENT
            # ====================================

            if len(diff) == 0:
                stop_reason = "aucune modification"

                log_warn(
                    f"Arrêt anticipé : aucune modification ({path})"
                )

                return {
                    "success": False,
                    "attempts": attempt,
                    "initial_errors": initial["errors"],
                    "final_errors": current["errors"],
                    "backup_path": backup_path,
                    "diff": diff,
                    "diff_lines": len(diff),
                    "stop_reason": stop_reason
                }

            # ====================================
            # ARRÊT ANTICIPÉ — SCORE DÉGRADÉ
            # ====================================

            if after_score["score"] < before_score["score"]:
                stop_reason = "score dégradé"

                log_warn(
                    f"Arrêt anticipé : score dégradé ({path})"
                )

                return {
                    "success": False,
                    "attempts": attempt,
                    "initial_errors": initial["errors"],
                    "final_errors": current["errors"],
                    "backup_path": backup_path,
                    "diff": diff,
                    "diff_lines": len(diff),
                    "stop_reason": stop_reason
                }

            # ====================================
            # ARRÊT ANTICIPÉ — ERREURS IDENTIQUES
            # ====================================

            if after_errors == before_errors:
                stop_reason = "erreurs inchangées"

                log_warn(
                    f"Arrêt anticipé : erreurs inchangées ({path})"
                )

                return {
                    "success": False,
                    "attempts": attempt,
                    "initial_errors": initial["errors"],
                    "final_errors": current["errors"],
                    "backup_path": backup_path,
                    "diff": diff,
                    "diff_lines": len(diff),
                    "stop_reason": stop_reason
                }

            before_score = after_score
            before_errors = after_errors

            if current["valid"]:
                log_info(f"Fichier corrigé en {attempt} tentative(s) : {path}")
                return {
                    "success": True,
                    "attempts": attempt,
                    "initial_errors": initial["errors"],
                    "final_errors": [],
                    "backup_path": backup_path,
                    "diff": diff,
                    "diff_lines": len(diff),
                    "stop_reason": stop_reason
                }

        final = validate_file(path)
        log_warn(f"Échec correction après {max_attempts} tentatives : {path}")
        return {
            "success": False,
            "attempts": max_attempts,
            "initial_errors": initial["errors"],
            "final_errors": final["errors"],
            "backup_path": backup_path,
            "diff": diff,
            "diff_lines": len(diff),
            "stop_reason": stop_reason
        }

    except Exception as e:
        return {
            "success": False,
            "attempts": 0,
            "initial_errors": [],
            "final_errors": [str(e)],
            "backup_path": backup_path,
            "diff": diff,
            "diff_lines": len(diff),
            "stop_reason": stop_reason
        }


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
