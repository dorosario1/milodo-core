SKILL_NAME = 'shopify_audit'
SKILL_DESCRIPTION = 'créer un skill shopify_audit.py dans skills/ qui contient une classe ShopifyAuditor avec SKILL_NAME, SKILL_DESCRIPTION, SKILL_VERSION, EXECUTION_PROFILE=web, et ces méthodes :  1. scan_theme(theme_path) — lit récursivement tous les fichiers .liquid et .json du thème 2. detect_ui_issues(theme_path) — détecte les problèmes courants : contrastes faibles, padding manquant, overflow, bandes blanches, texte trop grand/petit, CTA peu visibles 3. suggest_fixes(issues) — pour chaque problème, propose un correctif Liquid ou CSS 4. apply_fix(theme_path, issue_id) — applique un correctif spécifique avec backup .bak 5. generate_report(theme_path) — génère un rapport complet des problèmes et correctifs  Utilise Python standard library uniquement (pathlib, json, re).'
SKILL_VERSION = "1.0.0"

import pathlib
import json
import re

class ShopifyAuditor:
    SKILL_NAME = "shopify_audit"
    SKILL_DESCRIPTION = "Analyse les thèmes Shopify pour détecter les problèmes courants et proposer des correctifs."
    SKILL_VERSION = "1.0"

    EXECUTION_PROFILE = 'web'

    def __init__(self, theme_path):
        self.theme_path = theme_path
        self.issues = []

    def scan_theme(self, theme_path):
        for file in theme_path.rglob('*.liquid') | theme_path.rglob('*.json'):
            with open(file, 'r') as f:
                content = f.read()
                if re.search(r'padding: \d{1,2}%', content):
                    self.issues.append({"issue": "padding manquant", "correctif": "Ajouter un padding"})
                elif re.search(r'overflow: hidden', content):
                    self.issues.append({"issue": "ouverture masquée", "correctif": "Définir overflow: visible"})
                # Ajouter plus de règles ici

    def detect_ui_issues(self, theme_path):
        import re
        from pathlib import Path

        theme = Path(theme_path)
        issues = []

        # Scanner liquid ET css
        files = list(theme.rglob("*.liquid")) + list(theme.rglob("*.css"))

        dark_backgrounds = ["#000", "#111", "#1a1a2e", "#0f0f0f", "#121212", "#222", "#333"]

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                relative = str(file_path.relative_to(theme))
                file_issues = []

                # 1. Overflow / bandes blanches
                if ("max-width: 100%" not in content and "overflow-x: hidden" not in content
                    and "overflow-x:hidden" not in content):
                    if "header" in relative.lower() or relative.startswith("layout/"):
                        confidence = 0.90
                        file_issues.append({
                            "id": f"overflow_{file_path.stem}",
                            "severity": "medium",
                            "confidence": confidence,
                            "file": relative,
                            "type": "overflow_risk",
                            "description": "Risque de bandes blanches : pas de max-width:100% ou overflow-x:hidden sur header/layout",
                            "fix": "Ajouter overflow-x: hidden; max-width: 100vw; au container principal"
                        })

                # 2. Contraste noir sur fond sombre (amélioré)
                has_dark_text = re.search(r'color:\s*(#000|#000000|black|rgb\(0,\s*0,\s*0\))', content, re.IGNORECASE)
                has_dark_bg = any(bg in content for bg in dark_backgrounds)
                if has_dark_text and has_dark_bg:
                    confidence = 0.60
                    if "#333" in content:
                        confidence = 0.50
                    if any(bg in content for bg in ["#000", "#111", "#1a1a2e", "#0f0f0f", "#121212", "#222"]):
                        confidence = 0.80
                    file_issues.append({
                        "id": f"contrast_{file_path.stem}",
                        "severity": "medium",
                        "confidence": confidence,
                        "file": relative,
                        "type": "contrast",
                        "description": "Texte sombre sur fond sombre détecté : lisibilité potentiellement faible",
                        "fix": "Utiliser une couleur de texte claire (ex: color: #fff ou var(--color-foreground))"
                    })

                # 3. CTA potentiellement faibles
                if "button" in relative.lower() or "cta" in relative.lower() or "btn" in relative.lower():
                    if "font-size" not in content.lower() or "padding" not in content.lower():
                        confidence = 0.55 if "button" in relative.lower() and "font-size" not in content.lower() else 0.35
                        file_issues.append({
                            "id": f"cta_{file_path.stem}",
                            "severity": "low",
                            "confidence": confidence,
                            "file": relative,
                            "type": "cta_weak",
                            "description": "Composant bouton/CTA sans taille ou padding explicite",
                            "fix": "Définir font-size et padding pour améliorer la visibilité du CTA"
                        })

                if len(file_issues) > 1:
                    for issue in file_issues:
                        issue["confidence"] = min(issue["confidence"] + 0.05, 1.0)

                issues.extend(file_issues)

            except Exception:
                continue

        return {
            "success": True,
            "theme": str(theme_path),
            "files_scanned": len(files),
            "issues": issues,
            "summary": {
                "critical": len([i for i in issues if i["severity"] == "critical"]),
                "medium": len([i for i in issues if i["severity"] == "medium"]),
                "low": len([i for i in issues if i["severity"] == "low"]),
                "total": len(issues)
            }
        }

    def suggest_fixes(self, issues):
        fixes = []
        for issue in issues:
            if issue['issue'] == 'padding manquant':
                fixes.append({"correctif": "Ajouter un padding", "liquid": f"{{ liquid | padding: 10px }}"})
            elif issue['issue'] == 'ouverture masquée':
                fixes.append({"correctif": "Définir overflow: visible", "css": f".class {{ overflow: visible; }}"})
        return fixes

    def apply_fix(self, theme_path, issue_id):
        """
        Applique un correctif safe avec backup .bak.
        Uniquement pour les issues confidence >= 0.7
        """
        import shutil
        from pathlib import Path

        theme = Path(theme_path)

        # 1. Trouver l'issue
        all_issues = self.detect_ui_issues(theme_path)
        issue = None
        for i in all_issues.get("issues", []):
            if i["id"] == issue_id:
                issue = i
                break

        if not issue:
            return {"success": False, "error": f"Issue introuvable : {issue_id}"}

        if issue.get("confidence", 0) < 0.7:
            return {"success": False, "error": f"Confiance trop faible ({issue['confidence']}), patch refusé"}

        # 2. Trouver le fichier
        file_path = theme / issue["file"]
        if not file_path.exists():
            return {"success": False, "error": f"Fichier introuvable : {file_path}"}

        # 3. Backup
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)

        # 4. Appliquer le fix selon le type
        content = file_path.read_text(encoding="utf-8", errors="replace")
        new_content = content

        issue_type = issue.get("type", "")

        if issue_type == "overflow_risk":
            # Ajouter overflow-x hidden dans le premier container
            if "overflow-x" not in content:
                new_content = content.replace(
                    "class=\"",
                    'style="overflow-x: hidden; max-width: 100vw;" class=\"',
                    1
                )

        elif issue_type == "contrast":
            # Remplacer color sombre par clair
            import re
            new_content = re.sub(
                r'color:\s*(#000|#000000|black)',
                'color: #ffffff',
                content,
                count=1,
                flags=re.IGNORECASE
            )

        elif issue_type == "cta_weak":
            # Ajouter padding et font-size au premier bouton
            if "button" in content.lower():
                new_content = content.replace(
                    "class=\"button",
                    'style="font-size: 1rem; padding: 12px 24px;" class="button',
                    1
                )

        else:
            backup_path.unlink()
            return {"success": False, "error": f"Type de fix non supporté : {issue_type}"}

        # 5. Écrire
        file_path.write_text(new_content, encoding="utf-8")

        return {
            "success": True,
            "issue_id": issue_id,
            "file": issue["file"],
            "type": issue_type,
            "backup": str(backup_path),
            "confidence": issue["confidence"]
        }

    def generate_report(self, theme_path):
        report = {"thème": theme_path.name}
        for issue in self.issues:
            report[f"{issue['issue']}_correctif"] = issue['correctif']
        return report


def run(action="generate_report", **kwargs):
    theme_path = kwargs.get("theme_path")
    theme_path = pathlib.Path(theme_path) if theme_path else pathlib.Path.cwd()
    auditor = ShopifyAuditor(theme_path)

    if action == "generate_report":
        return auditor.generate_report(theme_path)
    elif action == "scan_theme":
        return auditor.scan_theme(theme_path)
    elif action == "detect_ui_issues":
        return auditor.detect_ui_issues(theme_path)
    elif action == "suggest_fixes":
        issues = kwargs.get("issues", [])
        return auditor.suggest_fixes(issues)
    elif action == "apply_fix":
        issue_id = kwargs.get("issue_id")
        return auditor.apply_fix(theme_path, issue_id)
    else:
        return {"success": False, "error": f"Action inconnue: {action}"}
