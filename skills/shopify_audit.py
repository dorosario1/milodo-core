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
    PATCH_HISTORY_FILE = ".milodo/patch_history.json"

    def _log_patch(self, entry):
        try:
            from pathlib import Path
            import json
            from datetime import datetime

            history_file = Path(self.PATCH_HISTORY_FILE)
            history_file.parent.mkdir(parents=True, exist_ok=True)

            history = []
            if history_file.exists():
                try:
                    history = json.loads(history_file.read_text(encoding="utf-8"))
                except:
                    history = []

            entry["timestamp"] = datetime.now().isoformat()
            entry["patch_version"] = "v2"
            history.append(entry)
            history = history[-200:]

            tmp = history_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(history_file)
        except Exception as log_error_exc:
            from logger import log_error
            log_error(f"Patch history write failed: {log_error_exc}")

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
                has_dark_text = re.search(r'(^|[;{\s])color:\s*(#000000|#000(?![0-9a-fA-F])|black|rgb\(0,\s*0,\s*0\))', content, re.IGNORECASE | re.MULTILINE)
                has_dark_bg = any(re.search(r'(^|[;{\s])background(?:-color)?:\s*' + re.escape(bg) + r'(?![0-9a-fA-F])', content, re.IGNORECASE | re.MULTILINE) for bg in dark_backgrounds)
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
        import re
        from pathlib import Path
        from logger import log_error

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
                if 'style="' in content:
                    new_content = content.replace(
                        'style="',
                        'style="overflow-x: hidden; max-width: 100vw; ',
                        1
                    )
                else:
                    new_content = content.replace(
                        "class=\"",
                        'style="overflow-x: hidden; max-width: 100vw;" class=\"',
                        1
                    )

        elif issue_type == "contrast":
            # Remplacer color sombre par clair
            new_content = re.sub(
                r'(^|[;{\s])color:\s*(#000000|#000(?![0-9a-fA-F])|black)',
                r'\1color: #ffffff',
                content,
                count=1,
                flags=re.IGNORECASE | re.MULTILINE
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

        # 6. Validation post-patch
        try:
            new_content_check = file_path.read_text(encoding="utf-8", errors="replace")

            if len(new_content_check) == 0:
                raise ValueError("Fichier vide après patch")

            if len(new_content_check) < len(content) * 0.5:
                raise ValueError(f"Fichier tronqué : {len(new_content_check)} < {len(content) * 0.5}")

            # Vérifier balises HTML uniquement pour .liquid et .html
            if file_path.suffix in (".liquid", ".html") and issue_type in ("overflow_risk", "contrast"):
                if "<" not in new_content_check or ">" not in new_content_check:
                    raise ValueError("HTML corrompu : balises manquantes")
                if re.search(r'<[^>]*\sstyle="[^"]*"[^>]*\sstyle="', new_content_check, re.IGNORECASE):
                    raise ValueError("HTML corrompu : attribut style dupliqué")

        except Exception as e:
            # Log + rollback (garder le .bak pour inspection)
            log_error(f"Validation failed after patch: {e}")
            shutil.copy2(backup_path, file_path)
            try:
                self._log_patch({
                    "issue_id": issue_id,
                    "file": issue["file"],
                    "type": issue_type,
                    "confidence": issue["confidence"],
                    "success": False,
                    "rolled_back": True,
                    "error": str(e),
                    "backup_path": str(backup_path)
                })
            except Exception:
                pass
            return {
                "success": False,
                "error": f"Validation failed, rollback : {e}",
                "issue_id": issue_id,
                "rolled_back": True,
                "backup_kept": str(backup_path)
            }

        try:
            self._log_patch({
                "issue_id": issue_id,
                "file": issue["file"],
                "type": issue_type,
                "confidence": issue["confidence"],
                "success": True,
                "rolled_back": False,
                "backup_path": str(backup_path)
            })
        except Exception:
            pass

        return {
            "success": True,
            "issue_id": issue_id,
            "file": issue["file"],
            "type": issue_type,
            "backup": str(backup_path),
            "confidence": issue["confidence"]
        }

    def apply_multiple_fixes(self, theme_path, min_confidence=0.8, max_fixes=3, stop_on_failures=2):
        import time

        report = self.detect_ui_issues(theme_path)
        candidates = [i for i in report["issues"] if i.get("confidence", 0) >= min_confidence]
        candidates.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        results = []
        success_count = 0
        failure_count = 0
        rollback_count = 0
        seen_files = set()

        for issue in candidates:
            if issue["file"] in seen_files:
                continue
            seen_files.add(issue["file"])

            if len(results) >= max_fixes:
                break

            start_time = time.time()
            result = self.apply_fix(theme_path, issue["id"])
            duration_ms = int((time.time() - start_time) * 1000)

            if not isinstance(result, dict):
                result = {"success": False, "error": "Invalid apply_fix result"}

            result["duration_ms"] = duration_ms

            if result.get("success"):
                success_count += 1
            elif result.get("rolled_back"):
                rollback_count += 1
                failure_count += 1
            else:
                failure_count += 1

            results.append(result)

            if failure_count >= stop_on_failures:
                break

        return {
            "success": failure_count == 0,
            "total_candidates": len(candidates),
            "applied": len(results),
            "success_count": success_count,
            "failure_count": failure_count,
            "rollback_count": rollback_count,
            "stopped_early": failure_count >= stop_on_failures,
            "results": results
        }

    def dry_run(self, theme_path, min_confidence=0.7, max_preview=5):
        from pathlib import Path

        report = self.detect_ui_issues(theme_path)
        candidates = [i for i in report["issues"] if i.get("confidence", 0) >= min_confidence]
        candidates.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        previews = []
        seen_files = set()

        for issue in candidates:
            # Éviter les doublons de fichier
            if issue["file"] in seen_files:
                continue
            seen_files.add(issue["file"])

            if len(previews) >= max_preview:
                break

            file_path = Path(theme_path) / issue["file"]

            # Calculer le risque estimé
            conf = issue["confidence"]
            if conf >= 0.9:
                estimated_risk = "low"
            elif conf >= 0.75:
                estimated_risk = "medium"
            else:
                estimated_risk = "high"

            preview = {
                "issue_id": issue["id"],
                "file": issue["file"],
                "confidence": conf,
                "severity": issue["severity"],
                "type": issue["type"],
                "description": issue["description"],
                "fix_suggestion": issue.get("fix", ""),
                "file_exists": file_path.exists(),
                "estimated_risk": estimated_risk,
                "would_patch": True
            }
            previews.append(preview)

        return {
            "success": True,
            "mode": "dry-run",
            "theme": str(theme_path),
            "total_issues": len(report["issues"]),
            "candidates": len(candidates),
            "previews": previews,
            "summary": {
                "high_confidence": len([p for p in previews if p["confidence"] >= 0.85]),
                "medium_confidence": len([p for p in previews if 0.7 <= p["confidence"] < 0.85]),
                "files_affected": len(set(p["file"] for p in previews))
            }
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
    elif action == "dry_run":
        min_confidence = kwargs.get("min_confidence", 0.7)
        max_preview = kwargs.get("max_preview", 5)
        return auditor.dry_run(theme_path, min_confidence, max_preview)
    elif action == "apply_multiple_fixes":
        min_confidence = kwargs.get("min_confidence", 0.8)
        max_fixes = kwargs.get("max_fixes", 3)
        return auditor.apply_multiple_fixes(theme_path, min_confidence, max_fixes)
    elif action == "apply_fix":
        issue_id = kwargs.get("issue_id")
        return auditor.apply_fix(theme_path, issue_id)
    else:
        return {"success": False, "error": f"Action inconnue: {action}"}
