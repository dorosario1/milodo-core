import difflib
from pathlib import Path

import intelligence
from file_tools import read_file, write_file, exists
from logger import log_info, log_error, log_warn, log_debug
from state_recall import get_last_project


SCORE_HISTORY_FILE = (
    Path(".milodo")
    / "score_history.json"
)


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


MUTATIONS = {
    "layout": [
        "hero classique centré",
        "hero fullscreen avec image background",
        "hero split gauche-texte droite-image",
        "pas de hero, cards directement"
    ],

    "style": [
        "design sombre #1a1a2e",
        "design clair minimaliste",
        "glassmorphism avec backdrop-filter",
        "neumorphism soft"
    ],

    "structure": [
        "navigation classique en haut",
        "navigation latérale fixe",
        "menu hamburger mobile-first",
        "footer expansif avec 4 colonnes"
    ]
}


def mutate_prompt(
    base_prompt,
    generation
):
    """
    Ajoute des variations
    structurelles au prompt.
    """

    import random

    random.seed(generation)

    layout = MUTATIONS[
        "layout"
    ][
        generation
        % len(
            MUTATIONS["layout"]
        )
    ]

    style = MUTATIONS[
        "style"
    ][
        generation
        % len(
            MUTATIONS["style"]
        )
    ]

    structure = MUTATIONS[
        "structure"
    ][
        generation
        % len(
            MUTATIONS["structure"]
        )
    ]

    return f"""
{base_prompt}

VARIATION UNIQUE
(génération {generation}) :

- Layout : {layout}

- Style : {style}

- Structure : {structure}

IMPORTANT :
Cette génération doit être
VISIBLEMENT DIFFÉRENTE
des autres générations.

EXIGENCES :
- HTML5 valide
- responsive
- CSS moderne
- structure originale
- sections bien séparées
- UI cohérente
"""


def save_score(
    template_type,
    project_name,
    score,
    path
):
    """
    Sauvegarde un score
    dans l'historique.
    """

    import json
    from datetime import datetime

    try:
        Path(".milodo").mkdir(
            exist_ok=True
        )

        history = []

        if SCORE_HISTORY_FILE.exists():
            try:
                history = json.loads(
                    SCORE_HISTORY_FILE.read_text(
                        encoding="utf-8"
                    )
                )
            except Exception:
                history = []

        if not isinstance(history, list):
            history = []

        entry = {
            "template": template_type,
            "project": project_name,
            "score": score,
            "path": path,
            "date": datetime.now().isoformat()
        }

        history.insert(0, entry)

        history = history[:100]

        SCORE_HISTORY_FILE.write_text(
            json.dumps(
                history,
                indent=2,
                ensure_ascii=False
            ) + "\n",
            encoding="utf-8"
        )

        log_info(
            f"Score sauvegardé : "
            f"{template_type} "
            f"{score}/100"
        )

        return True

    except Exception as e:
        log_warn(
            f"Historique score impossible : {e}"
        )

        return False


def get_best_scores(
    template_type=None,
    limit=5
):
    """
    Retourne les meilleurs scores.
    """

    import json

    try:
        if not SCORE_HISTORY_FILE.exists():
            return []

        history = json.loads(
            SCORE_HISTORY_FILE.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(history, list):
            return []

        if template_type:
            history = [
                item for item in history
                if item.get("template") == template_type
            ]

        history.sort(
            key=lambda x: x.get(
                "score",
                0
            ),
            reverse=True
        )

        return history[:limit]

    except Exception:
        return []


def get_average_score(
    template_type=None
):
    """
    Retourne le score moyen.
    """

    import json

    try:
        if not SCORE_HISTORY_FILE.exists():
            return 0

        history = json.loads(
            SCORE_HISTORY_FILE.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(history, list):
            return 0

        if template_type:
            history = [
                item for item in history
                if item.get("template") == template_type
            ]

        scores = [
            item.get("score", 0)
            for item in history
        ]

        if not scores:
            return 0

        return sum(scores) / len(scores)

    except Exception:
        return 0


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


def generate_with_retry(
    prompt,
    path,
    max_retries=2,
    min_score=70
):
    """
    Génère du code avec retry automatique
    si qualité insuffisante.
    """

    from validate_file import quality_score

    current_prompt = prompt
    score = 0

    for attempt in range(max_retries + 1):
        log_info(
            f"Retry generation attempt "
            f"{attempt + 1}/"
            f"{max_retries + 1}"
        )

        generated = generate_code(current_prompt)

        if not generated:

            log_warn(
                f"Génération vide : {path}"
            )

            continue

        generated = clean_llm_output(generated)

        write_file(path, generated)

        fix_result = auto_fix_loop(path)

        score_result = quality_score(path)

        score = score_result.get("score", 0)

        log_info(
            f"Score génération : "
            f"{score}/100"
        )

        if score >= min_score:
            return {
                "success": True,
                "score": score,
                "retries": attempt,
                "path": path,
                "fix_result": fix_result
            }

        current_prompt = (
            current_prompt
            + "\n\n"
            + "AMÉLIORATIONS DEMANDÉES : "
            + "code HTML5 valide, "
            + "design responsive, "
            + "contenu riche >500 caractères, "
            + "CSS inclus, "
            + "navigation complète"
        )

        log_warn(
            f"Retry nécessaire : "
            f"score {score} < {min_score}"
        )

    return {
        "success": False,
        "score": score,
        "retries": max_retries,
        "path": path
    }


def rank_templates(
    project_name,
    template_types=None,
    output_base="rank_test"
):
    """
    Compare plusieurs templates
    et retourne le meilleur.
    """

    if template_types is None:
        template_types = [
            "restaurant",
            "portfolio",
            "landing",
            "shop"
        ]

    from pathlib import Path
    from validate_file import quality_score

    rankings = []

    for template_type in template_types:
        try:
            output_dir = (
                Path(output_base)
                / template_type
            )

            result = generate_from_template(
                template_type,
                project_name,
                str(output_dir)
            )

            if not result.get("success"):

                log_warn(
                    f"Template échoué : "
                    f"{template_type}"
                )

                continue

            scores = []

            for file_path in result.get(
                "files_created",
                []
            ):
                try:

                    score_result = quality_score(
                        file_path
                    )

                    scores.append(
                        score_result.get(
                            "score",
                            0
                        )
                    )

                except Exception as score_error:

                    log_warn(
                        f"Score impossible : "
                        f"{file_path} : "
                        f"{score_error}"
                    )

            average_score = (
                sum(scores) / len(scores)
                if scores else 0
            )

            log_info(
                f"Template "
                f"{template_type} : "
                f"{average_score}/100"
            )

            rankings.append({
                "type": template_type,
                "score": average_score,
                "files": result.get(
                    "files_created",
                    []
                )
            })

        except Exception as template_error:

            log_warn(
                f"Erreur template "
                f"{template_type} : "
                f"{template_error}"
            )

    rankings.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    if not rankings:

        return {
            "rankings": [],
            "best": None,
            "best_score": 0
        }

    best = rankings[0]

    return {
        "rankings": rankings,
        "best": best["type"],
        "best_score": best["score"]
    }


def evolve_template(template_type, project_name, generations=3, output_base="evolution_test"):
    """
    Évolution auto : génère N variantes, garde la meilleure, itère.
    """

    from validate_file import fitness_score

    best_generation = None
    best_score = 0
    best_dir = ""
    evolution = []

    for generation in range(1, generations + 1):
        try:
            output_dir = Path(output_base) / f"gen_{generation}"
            past_scores = get_best_scores(template_type, limit=1)
            evolved_project_name = mutate_prompt(
                project_name,
                generation
            )

            if past_scores:
                best_past_score = past_scores[0].get("score", 0)
                evolved_project_name += (
                    "\n\n"
                    f"Objectif : score > {best_past_score}. "
                    "Code HTML5 riche, CSS responsive, contenu > 500 caractères."
                )

            result = generate_from_template(
                template_type,
                evolved_project_name,
                str(output_dir)
            )

            if not result.get("success"):
                log_warn(f"Génération échouée : {template_type} gen {generation}")
                evolution.append({
                    "gen": generation,
                    "score": 0
                })
                continue

            scores = []

            for file_path in result.get("files_created", []):
                try:
                    score_result = fitness_score(file_path)
                    scores.append(score_result.get("fitness", 0))
                except Exception as score_error:
                    log_warn(f"Fitness impossible : {file_path} : {score_error}")

            average_score = (
                sum(scores) / len(scores)
                if scores else 0
            )

            save_score(
                template_type,
                project_name,
                average_score,
                str(output_dir)
            )

            evolution.append({
                "gen": generation,
                "score": average_score
            })

            log_info(
                f"Évolution template {template_type} "
                f"gen {generation}: fitness {average_score}/100"
            )

            if best_generation is None or average_score > best_score:
                best_generation = generation
                best_score = average_score
                best_dir = str(output_dir)

        except Exception as generation_error:
            log_warn(
                f"Erreur évolution template "
                f"{template_type} gen {generation}: "
                f"{generation_error}"
            )
            evolution.append({
                "gen": generation,
                "score": 0
            })

    initial_score = evolution[0]["score"] if evolution else 0

    return {
        "best_generation": best_generation,
        "best_score": best_score,
        "best_dir": best_dir,
        "evolution": evolution,
        "improvement": best_score - initial_score
    }


def crossover_evolve(
    template_type,
    project_name,
    generations=3,
    output_base="crossover_test"
):
    """
    Évolution avec crossover :
    fusionne les meilleurs éléments
    de chaque génération.
    """

    try:

        from pathlib import Path
        from validate_file import fitness_score
        import re

        evolution_result = evolve_template(
            template_type,
            project_name,
            generations=generations,
            output_base=output_base
        )

        evolution = evolution_result.get(
            "evolution",
            []
        )

        if not evolution:
            return {
                "success": False,
                "error": "Aucune génération"
            }

        generation_dirs = []

        for item in evolution:

            gen_number = item.get("gen")

            gen_dir = (
                Path(output_base)
                / f"gen_{gen_number}"
            )

            generation_dirs.append({
                "gen": gen_number,
                "dir": gen_dir,
                "score": item.get("score", 0)
            })

        sections = {
            "hero": None,
            "features": None,
            "pricing": None,
            "testimonials": None,
            "contact": None,
            "footer": None,
            "navigation": None
        }

        def section_richness(content):

            text = re.sub(
                r"<[^>]+>",
                " ",
                content
            )

            words = len(text.split())

            tags = len(
                re.findall(
                    r"<[a-zA-Z]",
                    content
                )
            )

            return words + tags

        for generation in generation_dirs:

            gen_dir = generation["dir"]

            if not gen_dir.exists():
                continue

            html_files = list(
                gen_dir.rglob("*.html")
            )

            for html_file in html_files:

                try:

                    content = html_file.read_text(
                        encoding="utf-8"
                    )

                    lower = content.lower()

                    for section in sections.keys():

                        if section in lower:

                            richness = section_richness(
                                content
                            )

                            current = sections[section]

                            if (
                                current is None
                                or richness > current["richness"]
                            ):

                                sections[section] = {
                                    "gen": generation["gen"],
                                    "richness": richness,
                                    "file": str(html_file)
                                }

                except Exception:
                    continue

        fusion_description = []

        for section, data in sections.items():

            if data:

                fusion_description.append(
                    f"{section} de gen_{data['gen']}"
                )

        crossover_prompt = f"""
Créer une landing page hybride.

Fusionner les meilleurs éléments :

{', '.join(fusion_description)}

IMPORTANT :
- HTML5 valide
- responsive
- contenu riche
- navigation moderne
- footer complet
- sections cohérentes
- design premium
"""

        crossover_dir = (
            Path(output_base)
            / "crossover"
        )

        crossover_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        crossover_file = (
            crossover_dir
            / "index.html"
        )

        retry_result = generate_with_retry(
            crossover_prompt,
            str(crossover_file),
            max_retries=2,
            min_score=70
        )

        crossover_fitness = fitness_score(
            str(crossover_file)
        )

        best_classic = max(
            evolution,
            key=lambda x: x.get("score", 0)
        )

        crossover_score = crossover_fitness.get(
            "fitness",
            0
        )

        improvement = (
            crossover_score
            - best_classic.get("score", 0)
        )

        log_info(
            f"Crossover fitness : "
            f"{crossover_score}/100"
        )

        return {
            "success": True,
            "best_classic": {
                "gen": best_classic.get("gen"),
                "score": best_classic.get("score")
            },
            "best_crossover": {
                "score": crossover_score
            },
            "improvement": improvement,
            "crossover_file": str(crossover_file),
            "sections": sections,
            "retry_result": retry_result
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


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
    rolled_back = False

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
                "stop_reason": stop_reason,
                "rolled_back": rolled_back
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
                    "stop_reason": stop_reason,
                    "rolled_back": rolled_back
                }

            # ====================================
            # ROLLBACK SI SCORE DÉGRADÉ
            # ====================================

            if after_score["score"] < before_score["score"]:

                log_warn(
                    f"Dégradation qualité : "
                    f"{before_score['score']} → "
                    f"{after_score['score']}"
                )

                try:

                    backup_content = read_file(backup_path)

                    if backup_content:

                        write_file(path, backup_content)

                        rolled_back = True

                        log_info(
                            f"Rollback effectué depuis "
                            f"{backup_path}"
                        )

                except Exception as rollback_error:

                    log_error(
                        f"Rollback impossible : "
                        f"{rollback_error}"
                    )

                stop_reason = "rollback"

                return {
                    "success": False,
                    "attempts": attempt,
                    "initial_errors": initial["errors"],
                    "final_errors": current["errors"],
                    "backup_path": backup_path,
                    "diff": diff,
                    "diff_lines": len(diff),
                    "stop_reason": stop_reason,
                    "rolled_back": rolled_back,
                    "score_before": before_score["score"],
                    "score_after": after_score["score"]
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
                    "stop_reason": stop_reason,
                    "rolled_back": rolled_back
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
                    "stop_reason": stop_reason,
                    "rolled_back": rolled_back
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
            "stop_reason": stop_reason,
            "rolled_back": rolled_back
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
            "stop_reason": stop_reason,
            "rolled_back": rolled_back
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
