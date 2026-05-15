SKILL_NAME = "html_audit"
SKILL_DESCRIPTION = "Audite une page web via son URL et détecte les problèmes UI"
SKILL_VERSION = "1.0.0"

import urllib.request
from skills.heuristics_engine import analyze


class HTMLAuditor:
    def audit_url(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MILODO-HTMLAudit/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
            try:
                html = raw.decode("utf-8")
            except:
                html = raw.decode("latin-1", errors="replace")
        except Exception as e:
            return {"success": False, "error": str(e)}

        return analyze(html, url)


def run(action="audit_url", **kwargs):
    auditor = HTMLAuditor()
    if action == "audit_url":
        url = kwargs.get("url", "")
        return auditor.audit_url(url)
    return {"success": False, "error": f"Action inconnue: {action}"}
