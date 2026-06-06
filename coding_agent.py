import difflib
import time
from pathlib import Path

import intelligence
from file_tools import read_file, write_file, exists
from logger import log_info, log_error, log_warn, log_debug
from state_recall import get_last_project


SCORE_HISTORY_FILE = (
    Path(".milodo")
    / "score_history.json"
)

GENOME_DIR = ".milodo/genome"
NICHE_MEMORY_FILE = ".milodo/niche_memory.json"
runtime_signals = {"fallback_used": False, "timeout_occurred": False, "ia_success": False, "ollama_timeout": False, "fallback_triggered": False, "repair_attempt": False, "repair_success": False}


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


DESIGN_SPECIES = {
    "dark": {
        "style": "design sombre luxueux #1a1a2e, or et violet",
        "genome_dir": ".milodo/genome/dark",
        "description": "Dark premium - restaurants gastronomiques, tech, luxe"
    },
    "glass": {
        "style": "glassmorphism moderne, backdrop-filter, transparence, flou",
        "genome_dir": ".milodo/genome/glass",
        "description": "Glass modern - SaaS, startups, design avant-garde"
    },
    "minimal": {
        "style": "minimaliste épuré, blanc, espace, typographie, peu d'éléments",
        "genome_dir": ".milodo/genome/minimal",
        "description": "Minimal clean - portfolios, architectes, juridique"
    },
    "brutalist": {
        "style": "brutaliste, bold, couleurs vives, typographie massive, raw",
        "genome_dir": ".milodo/genome/brutalist",
        "description": "Brutalist bold - artistes, créatifs, mode"
    }
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


def save_to_genome(
    section_type,
    html_section,
    score,
    metadata=None
):
    """
    Sauvegarde une section performante
    dans la bibliothèque génétique.
    """

    import json
    from pathlib import Path
    from datetime import datetime

    metadata = metadata or {}

    genome_dir = Path(GENOME_DIR)
    genome_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    genome_file = genome_dir / f"{section_type}.json"

    entries = []

    try:

        if genome_file.exists():

            entries = json.loads(
                genome_file.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(entries, list):
                entries = []

    except Exception:
        entries = []

    entry = {
        "html": html_section,
        "score": score,
        "date": datetime.now().isoformat(),
        "project": metadata.get("project"),
        "template": metadata.get("template"),
    }

    entries.append(entry)

    entries = sorted(
        entries,
        key=lambda x: x.get("score", 0),
        reverse=True
    )[:20]

    genome_file.write_text(
        json.dumps(
            entries,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    log_info(
        f"Genome saved : "
        f"{section_type} "
        f"({score}/20)"
    )

    return {
        "success": True,
        "file": str(genome_file),
        "entries": len(entries)
    }


def get_best_from_genome(
    section_type,
    limit=3
):
    """
    Retourne les meilleures sections
    d'un type donné.
    """

    import json
    from pathlib import Path

    genome_file = (
        Path(GENOME_DIR)
        / f"{section_type}.json"
    )

    if not genome_file.exists():
        return []

    try:

        data = json.loads(
            genome_file.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(data, list):
            return []

        return sorted(
            data,
            key=lambda x: x.get("score", 0),
            reverse=True
        )[:limit]

    except Exception:
        return []


def list_genome():
    """
    Liste les types disponibles
    dans le génome.
    """

    from pathlib import Path
    import json

    genome_dir = Path(GENOME_DIR)

    if not genome_dir.exists():
        return {}

    output = {}

    for file in genome_dir.glob("*.json"):

        try:

            data = json.loads(
                file.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(data, list):
                continue

            output[file.stem] = len(data)

        except Exception:
            continue

    return output


def inject_genome_section(
    section_type,
    target_html
):
    """
    Remplace une section HTML
    par la meilleure du génome.
    """

    import re

    best = get_best_from_genome(
        section_type,
        limit=1
    )

    if not best:
        return target_html

    replacement = best[0].get(
        "html",
        ""
    )

    patterns = {
        "hero":
            r'<(?:section|div|header)[^>]*(?:class|id)=["\'][^"\']*hero[^"\']*["\'][^>]*>.*?</(?:section|div|header)>',

        "navigation":
            r'<nav[^>]*>.*?</nav>',

        "features":
            r'<(?:section|div)[^>]*(?:class|id)=["\'][^"\']*features?[^"\']*["\'][^>]*>.*?</(?:section|div)>',

        "footer":
            r'<footer[^>]*>.*?</footer>',

        "main":
            r'<main[^>]*>.*?</main>'
    }

    pattern = patterns.get(
        section_type
    )

    if not pattern:
        return target_html

    updated = re.sub(
        pattern,
        replacement,
        target_html,
        flags=re.DOTALL | re.IGNORECASE
    )

    log_info(
        f"Genome inject : "
        f"{section_type}"
    )

    return updated


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

    ask_intelligence_start_time = time.perf_counter()
    result = _ask_intelligence(full_prompt)
    log_info(
        f"IA timing _ask_intelligence: "
        f"{time.perf_counter() - ask_intelligence_start_time:.2f}s"
    )

    if not result:
        runtime_signals["fallback_used"] = True
        runtime_signals["timeout_occurred"] = True
        runtime_signals["fallback_triggered"] = True
        log_warn("Fallback coding - IA indisponible")
        return ""

    code = _clean_code_result(result)
    runtime_signals["ia_success"] = True
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
        runtime_signals["fallback_used"] = True
        runtime_signals["timeout_occurred"] = True
        runtime_signals["fallback_triggered"] = True
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

                generate_code_start_time = time.perf_counter()
                generated = generate_code(single_prompt)
                log_info(
                    f"IA timing generate_code: "
                    f"{time.perf_counter() - generate_code_start_time:.2f}s"
                )

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

    generate_multi_files_start_time = time.perf_counter()
    result = generate_multi_files(
        prompt=prompt,
        output_dir=output_dir,
        files_spec=template["files"]
    )
    log_info(
        f"IA timing generate_multi_files: "
        f"{time.perf_counter() - generate_multi_files_start_time:.2f}s"
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


def extract_sections(html_content):
    """
    Extrait les sections HTML identifiables d'un fichier.
    Retourne {"hero": "...", "nav": "...", "features": "...", "footer": "...", ...}
    """
    import re

    sections = {}

    # Navigation
    nav_match = re.search(
        r'<nav[^>]*>.*?</nav>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )

    if nav_match:
        sections["navigation"] = nav_match.group(0)

    # Header
    header_match = re.search(
        r'<header[^>]*>.*?</header>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )

    if header_match:
        sections["header"] = header_match.group(0)

    # Hero
    hero_match = re.search(
        r'<(?:section|div)[^>]*class="[^"]*hero[^"]*"[^>]*>.*?</(?:section|div)>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )

    if hero_match:
        sections["hero"] = hero_match.group(0)

    # Features
    features_match = re.search(
        r'<(?:section|div)[^>]*class="[^"]*features[^"]*"[^>]*>.*?</(?:section|div)>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )

    if features_match:
        sections["features"] = features_match.group(0)

    # Footer
    footer_match = re.search(
        r'<footer[^>]*>.*?</footer>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )

    if footer_match:
        sections["footer"] = footer_match.group(0)

    # Main
    main_match = re.search(
        r'<main[^>]*>.*?</main>',
        html_content,
        re.DOTALL | re.IGNORECASE
    )

    if main_match:
        sections["main"] = main_match.group(0)

    return sections


def structural_crossover(
    template_type,
    project_name,
    generations=3,
    output_base="structural_test"
):
    """
    Crossover structurel :
    extrait les meilleures sections HTML
    puis les assemble.
    """

    from pathlib import Path

    try:

        evolution_result = evolve_template(
            template_type,
            project_name,
            generations=generations,
            output_base=output_base
        )

        evolution_data = evolution_result.get(
            "evolution",
            []
        )

        section_pool = {}

        best_classic_score = evolution_result.get(
            "best_score",
            0
        )

        for generation_data in evolution_data:

            generation_number = generation_data.get(
                "gen"
            )

            generation_score = generation_data.get(
                "score",
                0
            )

            generation_dir = Path(
                output_base
            ) / f"gen_{generation_number}"

            if not generation_dir.exists():
                continue

            html_files = list(
                generation_dir.rglob("*.html")
            )

            for html_file in html_files:

                try:

                    content = read_file(
                        str(html_file)
                    )

                    if not content:
                        continue

                    extracted = extract_sections(
                        content
                    )

                    for section_name, section_html in extracted.items():

                        existing = section_pool.get(
                            section_name
                        )

                        if (
                            not existing
                            or generation_score > existing["score"]
                        ):
                            section_pool[section_name] = {
                                "html": section_html,
                                "score": generation_score,
                                "generation": generation_number
                            }

                except Exception as e:

                    log_warn(
                        f"Extraction sections impossible : {e}"
                    )

        assembled_sections = []

        sections_used = {}

        section_order = [
            "navigation",
            "header",
            "hero",
            "features",
            "main",
            "footer"
        ]

        for section_name in section_order:

            best_section = section_pool.get(
                section_name
            )

            if not best_section:
                continue

            assembled_sections.append(
                best_section["html"]
            )

            sections_used[section_name] = {
                "generation": best_section["generation"],
                "score": best_section["score"]
            }

        hybrid_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{project_name}</title>

<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
}}

section {{
    padding: 40px;
}}
</style>

</head>

<body>

{chr(10).join(assembled_sections)}

</body>
</html>
"""

        crossover_dir = Path(
            output_base
        ) / "structural"

        crossover_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        crossover_file = crossover_dir / "index.html"

        write_file(
            str(crossover_file),
            hybrid_html
        )

        auto_fix_loop(
            str(crossover_file)
        )

        from validate_file import fitness_score

        structural_score = fitness_score(
            str(crossover_file)
        )

        improvement = (
            structural_score.get("fitness", 0)
            - best_classic_score
        )

        log_info(
            f"Structural crossover fitness : "
            f"{structural_score.get('fitness', 0)}/100"
        )

        return {
            "best_classic": {
                "score": best_classic_score
            },

            "best_structural": {
                "fitness": structural_score.get(
                    "fitness",
                    0
                ),
                "sections_used": sections_used
            },

            "improvement": improvement,

            "crossover_file": str(
                crossover_file
            )
        }

    except Exception as e:

        return {
            "best_classic": {},
            "best_structural": {},
            "improvement": 0,
            "error": str(e)
        }


def genome_aware_generate(
    template_type,
    project_name,
    output_dir
):
    """
    Génère un projet en utilisant
    les meilleurs composants
    du génome.
    """

    import re

    genome_sections = {}

    section_types = [
        "hero",
        "navigation",
        "features",
        "footer",
        "main"
    ]

    prompt_parts = [
        f"Projet : {project_name}",
        "",
        "Génère une page HTML5 complète.",
        "Responsive.",
        "Design moderne.",
        "Contenu riche.",
    ]

    selected_sections = []

    for section_type in section_types:

        best = get_best_from_genome(
            section_type,
            limit=1
        )

        if not best:
            continue

        best_entry = best[0]

        genome_sections[section_type] = {
            "score": best_entry.get(
                "score",
                0
            )
        }

        selected_sections.append({
            "type": section_type,
            "score": best_entry.get("score", 0),
            "html": best_entry.get("html", "")
        })

    normalized_sections = {
        section["type"]: re.sub(
            r"\s+",
            "",
            section["html"]
        )
        for section in selected_sections
    }

    for section in selected_sections:
        section_type = section["type"]
        section_html = section["html"]
        normalized_html = normalized_sections[section_type]
        contained_in = next(
            (
                other["type"]
                for other in selected_sections
                if other["type"] != section_type
                and len(normalized_sections[other["type"]]) > len(normalized_html)
                and normalized_html
                and normalized_html in normalized_sections[other["type"]]
            ),
            None
        )

        if contained_in:
            prompt_parts.append(
                f"""
SECTION GÉNOME :
- Type : {section_type}
- Score : {section["score"]}
- HTML : déjà inclus dans {contained_in}
"""
            )
            continue

        prompt_parts.append(
            f"""
SECTION GÉNOME :
- Type : {section_type}
- Score : {section["score"]}

HTML :
{section_html}
"""
        )

    prompt_parts.append(
        """
IMPORTANT :
Inspire-toi fortement de ces structures,
mais améliore-les.
Ne copie pas exactement.
"""
    )

    enriched_prompt = "\n".join(
        prompt_parts
    )

    log_info(
        f"Genome-aware generation : "
        f"{template_type}"
    )

    generate_from_template_start_time = time.perf_counter()
    result = generate_from_template(
        template_type,
        enriched_prompt,
        output_dir
    )
    log_info(
        f"Genome timing generate_from_template: "
        f"{time.perf_counter() - generate_from_template_start_time:.2f}s"
    )

    result["genome_used"] = genome_sections

    return result


def genome_aware_evolve(
    template_type,
    project_name,
    generations=3,
    output_base="genome_evo"
):
    """
    Évolution avec injection
    automatique du génome.
    """

    from pathlib import Path

    try:
        from skills.genome_memory import (
            archive_generation,
            detect_regression,
            load_archives,
        )
    except Exception as e:
        archive_generation = None
        detect_regression = None
        load_archives = None
        log_warn(
            f"Genome memory indisponible : {e}"
        )

    if load_archives:
        try:
            load_archives_start_time = time.perf_counter()
            archives = load_archives()
            log_info(
                f"Genome timing load_archives: "
                f"{time.perf_counter() - load_archives_start_time:.2f}s"
            )
            best_archive = archives[0] if archives else None

            if best_archive:
                log_info(
                    f"Genome memory best archive : "
                    f"found=True, "
                    f"generation={best_archive.get('generation')}, "
                    f"score={best_archive.get('score')}, "
                    f"html_path={best_archive.get('html_path')}, "
                    f"genes={best_archive.get('genes')}"
                )
            else:
                log_info(
                    "Genome memory best archive : found=False"
                )
        except Exception as memory_error:
            log_warn(
                f"Genome memory load archives error : "
                f"{memory_error}"
            )

    evolution = []

    best_score = 0
    best_generation = None
    best_dir = None

    for generation in range(
        1,
        generations + 1
    ):

        try:

            generation_dir = (
                Path(output_base)
                / f"gen_{generation}"
            )

            generation_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            generation_prompt = mutate_prompt(
                project_name,
                generation
            )

            genome_aware_generate_start_time = time.perf_counter()
            result = genome_aware_generate(
                template_type,
                generation_prompt,
                str(generation_dir)
            )
            log_info(
                f"Genome timing genome_aware_generate: "
                f"{time.perf_counter() - genome_aware_generate_start_time:.2f}s"
            )

            html_files = list(
                generation_dir.rglob(
                    "*.html"
                )
            )

            generation_scores = []

            for html_file in html_files:

                try:

                    auto_fix_loop(
                        str(html_file)
                    )

                    from validate_file import (
                        fitness_score,
                        section_fitness
                    )

                    fitness_score_start_time = time.perf_counter()
                    fitness = fitness_score(
                        str(html_file)
                    )
                    log_info(
                        f"Genome timing fitness_score: "
                        f"{time.perf_counter() - fitness_score_start_time:.2f}s"
                    )

                    generation_scores.append(
                        fitness.get(
                            "fitness",
                            0
                        )
                    )

                    content = read_file(
                        str(html_file)
                    )

                    if archive_generation:
                        try:
                            archive_generation_start_time = time.perf_counter()
                            archived = archive_generation(
                                f"{project_name}_gen_{generation}_{html_file.stem}",
                                fitness.get(
                                    "fitness",
                                    0
                                ),
                                {},
                                content or "",
                                genome_dir=output_base
                            )
                            log_info(
                                f"Genome timing archive_generation: "
                                f"{time.perf_counter() - archive_generation_start_time:.2f}s"
                            )
                            log_info(
                                f"Genome memory archive : "
                                f"created={archived}, "
                                f"score={fitness.get('fitness', 0)}, "
                                f"file={html_file}"
                            )
                        except Exception as memory_error:
                            log_warn(
                                f"Genome memory archive error : "
                                f"{memory_error}"
                            )

                    sections = extract_sections(
                        content
                    )

                    section_scores = section_fitness(
                        content
                    )

                    section_data = (
                        section_scores.get(
                            "sections",
                            {}
                        )
                    )

                    mapping = {
                        "hero": "hero",
                        "navigation": "navigation",
                        "features": "features",
                        "footer": "footer",
                        "main": "main"
                    }

                    for (
                        section_name,
                        html_section
                    ) in sections.items():

                        if section_name not in mapping:
                            continue

                        local_score = (
                            section_data
                            .get(
                                section_name,
                                {}
                            )
                            .get(
                                "score",
                                0
                            )
                        )

                        if local_score <= 0:
                            continue

                        save_to_genome(
                            section_name,
                            html_section,
                            local_score,
                            metadata={
                                "project":
                                    project_name,

                                "template":
                                    template_type
                            }
                        )

                except Exception as e:

                    log_warn(
                        f"Genome evolve file error : {e}"
                    )

            average_score = 0

            if generation_scores:

                average_score = (
                    sum(generation_scores)
                    / len(generation_scores)
                )

            if detect_regression:
                try:
                    detect_regression_start_time = time.perf_counter()
                    regression = detect_regression(
                        average_score
                    )
                    log_info(
                        f"Genome timing detect_regression: "
                        f"{time.perf_counter() - detect_regression_start_time:.2f}s"
                    )
                    log_info(
                        f"Genome memory regression : "
                        f"detected={regression.get('regression_detected')}, "
                        f"current={regression.get('current_score')}, "
                        f"best={regression.get('best_historical')}, "
                        f"recommendation={regression.get('recommendation')}"
                    )
                except Exception as memory_error:
                    log_warn(
                        f"Genome memory regression error : "
                        f"{memory_error}"
                    )

            evolution.append({
                "gen": generation,
                "score": average_score,
                "dir": str(generation_dir)
            })

            log_info(
                f"Genome evolution gen "
                f"{generation} : "
                f"{average_score}/100"
            )

            if average_score > best_score:

                best_score = average_score
                best_generation = generation
                best_dir = str(generation_dir)

        except Exception as e:

            log_warn(
                f"Genome generation failed : {e}"
            )

            continue

    return {
        "best_generation": best_generation,
        "best_score": best_score,
        "best_dir": best_dir,
        "evolution": evolution,
        "genome_state": list_genome()
    }


def identify_weakest_section(
    html_path
):
    """
    Identifie la section
    la plus faible d'un HTML.
    """

    from validate_file import (
        section_fitness
    )

    from pathlib import Path

    content = Path(
        html_path
    ).read_text(
        encoding="utf-8"
    )

    sf = section_fitness(
        content
    )

    sections = sf.get(
        "sections",
        {}
    )

    weakest = None

    lowest_ratio = 1.0

    max_scores = {
        "hero": 20,
        "navigation": 15,
        "features": 15,
        "footer": 10,
        "main": 20
    }

    for (
        name,
        data
    ) in sections.items():

        if not data.get(
            "found"
        ):
            continue

        max_score = max_scores.get(
            name,
            10
        )

        if max_score <= 0:
            continue

        score = data.get(
            "score",
            0
        )

        ratio = score / max_score

        if ratio < lowest_ratio:

            lowest_ratio = ratio

            weakest = {
                "section": name,
                "score": score,
                "max_score": max_score,
                "ratio": round(
                    ratio,
                    2
                )
            }

    return weakest


def targeted_mutation(
    html_path,
    target_section,
    output_path=None
):
    """
    Mute uniquement
    une section spécifique.
    """

    from pathlib import Path

    from validate_file import (
        section_fitness
    )

    path = Path(
        html_path
    )

    output_path = (
        output_path
        or str(path)
    )

    original_html = path.read_text(
        encoding="utf-8"
    )

    sections = extract_sections(
        original_html
    )

    current_section = sections.get(
        target_section
    )

    if not current_section:

        return {
            "success": False,
            "error":
                f"Section introuvable : "
                f"{target_section}"
        }

    before_fitness = section_fitness(
        original_html
    )

    before_score = (
        before_fitness
        .get(
            "sections",
            {}
        )
        .get(
            target_section,
            {}
        )
        .get(
            "score",
            0
        )
    )

    prompt = f"""
Améliore cette section HTML.

SECTION :
{target_section}

HTML ACTUEL :
{current_section}

OBJECTIFS :
- design moderne
- responsive
- plus riche
- plus de contenu
- CTA améliorés
- meilleure structure
- HTML5 valide

IMPORTANT :
Garde le style global
du reste de la page.
Retourne UNIQUEMENT
la nouvelle section HTML.
"""

    generated = generate_code(
        prompt
    )

    if not generated:

        return {
            "success": False,
            "error":
                "Mutation vide"
        }

    generated = clean_llm_output(
        generated
    )

    updated_html = original_html.replace(
        current_section,
        generated,
        1
    )

    write_file(
        output_path,
        updated_html
    )

    auto_fix_loop(
        output_path
    )

    final_html = read_file(
        output_path
    )

    after_fitness = section_fitness(
        final_html
    )

    after_score = (
        after_fitness
        .get(
            "sections",
            {}
        )
        .get(
            target_section,
            {}
        )
        .get(
            "score",
            0
        )
    )

    improved = (
        after_score
        > before_score
    )

    return {
        "success": True,
        "section":
            target_section,
        "before_score":
            before_score,
        "after_score":
            after_score,
        "improvement":
            after_score
            - before_score,
        "improved":
            improved,
        "output_path":
            output_path
    }


def targeted_evolve(
    template_type,
    project_name,
    generations=3,
    output_base="targeted_test"
):
    """
    Évolution avec
    mutations ciblées.
    """

    from pathlib import Path

    from validate_file import (
        fitness_score
    )

    evolution = evolve_template(
        template_type,
        project_name,
        generations=generations,
        output_base=output_base
    )

    best_dir = evolution.get(
        "best_dir"
    )

    if not best_dir:

        return {
            "success": False,
            "error":
                "Aucune génération valide"
        }

    best_path = None

    html_files = list(
        Path(best_dir).rglob(
            "*.html"
        )
    )

    if html_files:
        best_path = str(
            html_files[0]
        )

    if not best_path:

        return {
            "success": False,
            "error":
                "Aucun HTML trouvé"
        }

    improvements = []

    current_fitness = fitness_score(
        best_path
    ).get(
        "fitness",
        0
    )

    for _ in range(3):

        weakest = identify_weakest_section(
            best_path
        )

        if not weakest:
            break

        section_name = weakest.get(
            "section"
        )

        mutation = targeted_mutation(
            best_path,
            section_name
        )

        new_fitness = fitness_score(
            best_path
        ).get(
            "fitness",
            0
        )

        improved = (
            new_fitness
            > current_fitness
        )

        if improved:

            current_fitness = new_fitness

            improvements.append({
                "section":
                    section_name,
                "fitness":
                    new_fitness,
                "improvement":
                    mutation.get(
                        "improvement",
                        0
                    )
            })

            log_info(
                f"Targeted mutation "
                f"success : "
                f"{section_name}"
            )

        else:

            rollback = (
                best_path
                + ".bak"
            )

            backup = read_file(
                rollback
            )

            if backup:

                write_file(
                    best_path,
                    backup
                )

                log_warn(
                    f"Rollback targeted "
                    f"mutation : "
                    f"{section_name}"
                )

            break

    return {
        "success": True,
        "best_path": best_path,
        "final_fitness":
            current_fitness,
        "improvements":
            improvements,
        "evolution":
            evolution
    }


def evolve_species(species_name, project_name, generations=2, output_base="species_test"):
    """
    Fait évoluer UNE espèce de design spécifique.
    Utilise le style et le génome propres à l'espèce.
    """

    from pathlib import Path
    from validate_file import section_fitness

    species = DESIGN_SPECIES.get(species_name)

    if not species:
        return {
            "success": False,
            "error": f"Espèce inconnue : {species_name}"
        }

    species_prompt = (
        f"{project_name}\n\n"
        f"ESPÈCE DESIGN : {species_name}\n"
        f"Style : {species.get('style')}\n"
        f"Description : {species.get('description')}\n"
        "Respecte fortement cette identité visuelle."
    )

    result = evolve_template(
        "landing",
        species_prompt,
        generations=generations,
        output_base=str(Path(output_base))
    )

    try:
        genome_dir = Path(species.get("genome_dir", ""))
        genome_dir.mkdir(parents=True, exist_ok=True)

        best_dir = result.get("best_dir")

        if best_dir:
            for html_file in Path(best_dir).rglob("*.html"):
                try:
                    content = read_file(str(html_file))
                    sections = extract_sections(content)
                    scores = section_fitness(content).get("sections", {})

                    for section_name, html_section in sections.items():
                        section_score = (
                            scores
                            .get(section_name, {})
                            .get("score", 0)
                        )

                        if section_score <= 0:
                            continue

                        original_genome_dir = globals().get("GENOME_DIR")
                        globals()["GENOME_DIR"] = str(genome_dir)
                        try:
                            save_to_genome(
                                section_name,
                                html_section,
                                section_score,
                                metadata={
                                    "project": project_name,
                                    "template": species_name,
                                }
                            )
                        finally:
                            globals()["GENOME_DIR"] = original_genome_dir
                except Exception as file_error:
                    log_warn(f"Genome espèce impossible : {file_error}")
    except Exception as genome_error:
        log_warn(f"Génome espèce impossible : {genome_error}")

    result["success"] = True
    result["species"] = species_name
    result["species_style"] = species.get("style")
    result["genome_dir"] = species.get("genome_dir")
    return result


def battle_species(project_name, species_list=None, generations=2, output_base="species_battle"):
    """
    Compétition entre espèces : fait évoluer chaque espèce et retourne la gagnante.
    """

    from pathlib import Path

    if species_list is None:
        species_list = list(DESIGN_SPECIES.keys())

    rankings = []
    all_results = {}

    for species_name in species_list:
        try:
            species_output = Path(output_base) / species_name
            result = evolve_species(
                species_name,
                project_name,
                generations=generations,
                output_base=str(species_output)
            )

            all_results[species_name] = result

            if not result.get("success"):
                log_warn(f"Espèce échouée : {species_name}")
                continue

            score = result.get("best_score", 0)

            rankings.append({
                "species": species_name,
                "score": score,
                "best_generation": result.get("best_generation"),
                "best_dir": result.get("best_dir"),
            })

            log_info(
                f"Species battle : "
                f"{species_name} "
                f"{score}/100"
            )

        except Exception as species_error:
            log_warn(
                f"Erreur espèce "
                f"{species_name} : "
                f"{species_error}"
            )

    rankings.sort(
        key=lambda item: item.get("score", 0),
        reverse=True
    )

    if not rankings:
        return {
            "winner": None,
            "winner_score": 0,
            "rankings": [],
            "all_results": all_results
        }

    winner = rankings[0]

    return {
        "winner": winner.get("species"),
        "winner_score": winner.get("score"),
        "rankings": rankings,
        "all_results": all_results
    }


def record_niche_result(
    niche,
    species,
    score
):
    """
    Enregistre le résultat
    d'une battle de niche.
    """

    import json
    from pathlib import Path
    from datetime import datetime

    memory_path = Path(
        NICHE_MEMORY_FILE
    )

    memory_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    data = {}

    try:

        if memory_path.exists():

            data = json.loads(
                memory_path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(data, dict):
                data = {}

    except Exception:
        data = {}

    niche_data = data.setdefault(
        niche,
        {}
    )

    species_data = niche_data.setdefault(
        species,
        {
            "wins": 0,
            "avg_score": 0,
            "scores": [],
            "last_used": None
        }
    )

    species_data["scores"].append(
        score
    )

    species_data["wins"] += 1

    species_data["avg_score"] = round(
        sum(
            species_data["scores"]
        ) / len(
            species_data["scores"]
        ),
        2
    )

    species_data["last_used"] = (
        datetime.now()
        .isoformat()
    )

    memory_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    log_info(
        f"Niche memory : "
        f"{niche} → "
        f"{species} "
        f"({score})"
    )

    return {
        "success": True,
        "niche": niche,
        "species": species,
        "avg_score":
            species_data["avg_score"]
    }


def predict_best_species(
    niche
):
    """
    Prédit la meilleure espèce
    pour une niche.
    """

    import json
    from pathlib import Path

    memory_path = Path(
        NICHE_MEMORY_FILE
    )

    if not memory_path.exists():
        return None

    try:

        data = json.loads(
            memory_path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return None

    niche_data = data.get(
        niche,
        {}
    )

    if not niche_data:
        return None

    total_battles = 0

    for species_data in niche_data.values():

        total_battles += species_data.get(
            "wins",
            0
        )

    if total_battles <= 0:
        return None

    best_species = None

    best_confidence = 0

    for (
        species,
        species_data
    ) in niche_data.items():

        wins = species_data.get(
            "wins",
            0
        )

        confidence = (
            wins / total_battles
        )

        avg_score = species_data.get(
            "avg_score",
            0
        )

        weighted = (
            confidence * 0.7
            + (avg_score / 100) * 0.3
        )

        if weighted > best_confidence:

            best_confidence = weighted

            best_species = {
                "species": species,
                "confidence": round(
                    confidence,
                    2
                ),
                "wins": wins,
                "avg_score": avg_score,
                "total_battles":
                    total_battles
            }

    return best_species


def smart_generate(
    niche,
    project_name,
    output_dir
):
    """
    Génération intelligente
    orientée niche.
    """

    prediction = predict_best_species(
        niche
    )

    selected_species = None

    method = None

    if (
        prediction
        and prediction.get(
            "confidence",
            0
        ) > 0.6
    ):

        selected_species = prediction.get(
            "species"
        )

        method = "predict"

        log_info(
            f"Smart predict : "
            f"{niche} → "
            f"{selected_species}"
        )

    else:

        battle = battle_species(
            project_name,
            generations=1
        )

        selected_species = battle.get(
            "winner"
        )

        winner_score = battle.get(
            "winner_score",
            0
        )

        if selected_species:

            record_niche_result(
                niche,
                selected_species,
                winner_score
            )

        method = "battle"

        log_info(
            f"Smart battle : "
            f"{niche} → "
            f"{selected_species}"
        )

    if not selected_species:

        return {
            "success": False,
            "error":
                "Aucune espèce valide"
        }

    species_data = DESIGN_SPECIES.get(
        selected_species,
        {}
    )

    enriched_prompt = (
        f"{project_name}\n\n"
        f"NICHE : {niche}\n"
        f"STYLE DOMINANT : "
        f"{species_data.get('style', '')}\n"
        f"DESCRIPTION : "
        f"{species_data.get('description', '')}\n"
    )

    result = generate_from_template(
        "landing",
        enriched_prompt,
        output_dir
    )

    result["species"] = (
        selected_species
    )

    result["method"] = method

    result["niche"] = niche

    result["prediction"] = prediction

    return result


def get_niche_stats():
    """
    Retourne les statistiques
    complètes niche → espèces.
    """

    import json
    from pathlib import Path

    memory_path = Path(
        NICHE_MEMORY_FILE
    )

    if not memory_path.exists():
        return {}

    try:

        data = json.loads(
            memory_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(data, dict):
            return {}

        return data

    except Exception:
        return {}


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
            runtime_signals["repair_attempt"] = True
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
                runtime_signals["repair_success"] = True
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
        runtime_signals["fallback_used"] = True
        runtime_signals["timeout_occurred"] = True
        runtime_signals["fallback_triggered"] = True
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
