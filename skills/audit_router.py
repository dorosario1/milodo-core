import re
import urllib.request


def detect_stack(url, html=None):
    if html:
        if "shopify" in html.lower() or "myshopify" in html.lower():
            return "shopify"
        if "wp-content" in html or "wordpress" in html.lower():
            return "wordpress"
    return "html"


def audit_url(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MILODO-AuditRouter/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        try:
            html = raw.decode("utf-8")
        except:
            html = raw.decode("latin-1", errors="replace")
    except Exception as e:
        return {"success": False, "error": str(e)}

    stack = detect_stack(url, html)

    if stack == "shopify":
        return {
            "success": True, "url": url, "stack": "shopify",
            "message": "Shopify detecte. Utilise 'audite dofitpro' pour un audit local.",
            "issues": [], "summary": {"total": 0}
        }

    from skills.heuristics_engine import analyze
    result = analyze(html, url)
    result["stack"] = stack
    return result


def run(action="audit_url", **kwargs):
    if action == "audit_url":
        return audit_url(kwargs.get("url", ""))
    return {"success": False, "error": f"Action inconnue: {action}"}
