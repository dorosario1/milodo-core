import hashlib


def group_issues(issues):
    """
    Regroupe les issues par type et zone UI.
    Retourne une liste de clusters.
    """
    clusters = {}

    for issue in issues:
        # Clé de regroupement : type + zone UI
        zone = _extract_zone(issue.get("file", ""))
        key = f"{issue.get('type', 'unknown')}:{zone}"

        if key not in clusters:
            clusters[key] = {
                "cluster_id": hashlib.sha1(key.encode()).hexdigest()[:8],
                "category": issue.get("type", "unknown"),
                "zone": zone,
                "issues": [],
                "files": [],
                "severity": "low",
                "confidence_sum": 0
            }

        cluster = clusters[key]
        cluster["issues"].append(issue)
        if issue["file"] not in cluster["files"]:
            cluster["files"].append(issue["file"])
        cluster["confidence_sum"] += issue.get("confidence", 0)

        # Mettre à jour la sévérité max
        if issue.get("severity") == "critical":
            cluster["severity"] = "critical"
        elif issue.get("severity") == "medium" and cluster["severity"] != "critical":
            cluster["severity"] = "medium"

    # Finaliser les clusters
    result = []
    for key, cluster in clusters.items():
        count = len(cluster["issues"])
        cluster["confidence_avg"] = round(cluster["confidence_sum"] / count, 2) if count > 0 else 0
        cluster["issue_count"] = count
        del cluster["confidence_sum"]
        result.append(cluster)

    # Trier par sévérité puis confiance
    severity_order = {"critical": 0, "medium": 1, "low": 2}
    result.sort(key=lambda c: (severity_order.get(c["severity"], 3), -c["confidence_avg"]))

    return result


def _extract_zone(file_path):
    """Extrait la zone UI d'un chemin de fichier."""
    file_lower = file_path.lower()
    if "header" in file_lower:
        return "header"
    elif "footer" in file_lower:
        return "footer"
    elif "product" in file_lower:
        return "product"
    elif "cart" in file_lower:
        return "cart"
    elif "layout" in file_lower:
        return "layout"
    elif "localization" in file_lower:
        return "localization"
    else:
        return "general"


def cluster_summary(clusters):
    """Génère un résumé textuel des clusters."""
    lines = []
    for c in clusters:
        emoji = {"critical": "[CRITICAL]", "medium": "[MEDIUM]", "low": "[LOW]"}.get(c["severity"], "")
        lines.append(f"{emoji} {c['category']} ({c['zone']}) - {c['issue_count']} issues, confiance {c['confidence_avg']:.0%}")
    return "\n".join(lines)
