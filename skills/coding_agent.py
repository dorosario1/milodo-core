import json
import shutil
from datetime import datetime
from pathlib import Path


WEIGHTS_PATH = Path(".milodo/heuristics_weights.json")
LOG_PATH = Path(".milodo/coding_agent.log")
BACKUPS_ROOT = Path(".milodo/backups")


def _log(message):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def load_weights():
    if not WEIGHTS_PATH.exists():
        return {}

    try:
        with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_issue_confidence(issue_type):
    weights = load_weights()
    return weights.get(issue_type, {}).get("confidence", 0.5)


def can_autofix(issue):
    issue_type = issue.get("type", "")
    confidence = get_issue_confidence(issue_type)
    return confidence >= 0.7


def generate_patch(issue, target_file, context=None):
    issue_type = issue.get("type", "")
    context = context or {}

    patches = {
        "no_h1": (
            f"Dans {target_file}, ajouter un <h1> clair et unique dans la zone hero, "
            "par exemple : <h1>Proposition de valeur principale</h1>."
        ),
        "hero_weak": (
            f"Dans {target_file}, renforcer le hero avec un <h1> explicite, "
            "un sous-texte utile et un CTA visible."
        ),
        "seo_missing": (
            f"Dans {target_file}, ajouter dans <head> : "
            '<meta name="description" content="Description claire et spécifique de la page.">'
        ),
        "whatsapp_below_fold": (
            f"Dans {target_file}, ajouter un bouton WhatsApp flottant visible dès le chargement, "
            'par exemple un lien fixe vers "https://wa.me/NUMERO".'
        ),
        "whatsapp_weak_message": (
            f"Dans {target_file}, utiliser une URL wa.me avec texte pré-rempli clair, "
            'par exemple ?text=Bonjour%20je%20souhaite%20plus%20d%27informations.'
        ),
        "form_too_long": (
            f"Dans {target_file}, réduire le nombre de champs visibles ou scinder le formulaire "
            "en plusieurs étapes courtes."
        ),
        "form_no_placeholder": (
            f"Dans {target_file}, ajouter des placeholders utiles aux champs, "
            'par exemple placeholder="Votre email".'
        ),
        "no_nav": (
            f"Dans {target_file}, ajouter une navigation sémantique <nav> avec les liens principaux."
        ),
        "navigation_missing": (
            f"Dans {target_file}, ajouter une navigation sémantique <nav> avec les liens principaux."
        ),
    }

    return patches.get(
        issue_type,
        f"Aucun patch spécialisé disponible pour {issue_type or 'unknown'} dans {target_file}.",
    )


def backup_file(target_file):
    source = Path(target_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUPS_ROOT / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / source.name

    if source.exists():
        shutil.copy2(source, backup_path)

    return str(backup_path)


def apply_patch(target_file, patch):
    return {
        "success": False,
        "message": "Patch application not implemented in V1",
    }


def fix_issue(issue, target_file, context=None, apply=False):
    issue_type = issue.get("type", "")
    confidence = get_issue_confidence(issue_type)
    patch = generate_patch(issue, target_file, context=context)
    mode = "apply" if apply else "dry-run"

    if not apply:
        result = {
            "success": True,
            "mode": mode,
            "issue_type": issue_type,
            "target_file": target_file,
            "confidence": confidence,
            "patch": patch,
            "message": "Patch generated in dry-run mode",
        }
        _log(
            f"issue_type={issue_type} target_file={target_file} "
            f"confidence={confidence} mode={mode} success=True"
        )
        return result

    if not can_autofix(issue):
        result = {
            "success": False,
            "mode": mode,
            "issue_type": issue_type,
            "target_file": target_file,
            "confidence": confidence,
            "patch": patch,
            "message": "Autofix refused: confidence below threshold",
        }
        _log(
            f"issue_type={issue_type} target_file={target_file} "
            f"confidence={confidence} mode={mode} success=False"
        )
        return result

    backup_path = backup_file(target_file)
    apply_result = apply_patch(target_file, patch)

    if not apply_result.get("success"):
        source = Path(target_file)
        backup = Path(backup_path)
        if source.exists() and backup.exists():
            shutil.copy2(backup, source)

        result = {
            "success": False,
            "mode": mode,
            "issue_type": issue_type,
            "target_file": target_file,
            "confidence": confidence,
            "patch": patch,
            "message": apply_result.get(
                "message",
                "Patch application failed and rollback attempted",
            ),
        }
        _log(
            f"issue_type={issue_type} target_file={target_file} "
            f"confidence={confidence} mode={mode} success=False"
        )
        return result

    result = {
        "success": True,
        "mode": mode,
        "issue_type": issue_type,
        "target_file": target_file,
        "confidence": confidence,
        "patch": patch,
        "message": "Patch applied",
    }
    _log(
        f"issue_type={issue_type} target_file={target_file} "
        f"confidence={confidence} mode={mode} success=True"
    )
    return result


def run(action="fix_issue", **kwargs):
    if action == "fix_issue":
        return fix_issue(
            issue=kwargs.get("issue", {}),
            target_file=kwargs.get("target_file", ""),
            context=kwargs.get("context"),
            apply=kwargs.get("apply", False),
        )

    return {
        "success": False,
        "error": f"Action inconnue: {action}",
    }
