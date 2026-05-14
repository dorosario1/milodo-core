import json
import re
import threading
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer
from skill_loader import create_skill
from coding_agent import generate_code
from logger import log_info, log_error, log_warn, log_debug


_server = None
_server_thread = None

PROJECT_PATHS = {
    "dofitpro": "C:/PROJECTS/DOFITPRO/theme"
}


class ChatRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        host = self.client_address[0]
        log_info(f"Connexion de {host}")
        log_debug(f"Requête HTTP : {self.path}")

        if self.path != "/chat":
            log_warn(f"Endpoint inconnu : {self.path}")
            self._send_json(404, {
                "success": False,
                "message": "Endpoint not found",
            })
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body) if raw_body else {}
            message = payload.get("message", "")
            response = handle_chat(message)
            self._send_json(200, response)
        except json.JSONDecodeError as error:
            log_warn(f"JSON invalide : {error}")
            self._send_json(400, {
                "success": False,
                "message": "Invalid JSON",
            })
        except Exception as error:
            log_error(f"HTTP error: {error}")
            self._send_json(500, {
                "success": False,
                "message": str(error),
            })

    def do_GET(self):
        host = self.client_address[0]
        log_info(f"Connexion de {host}")
        log_debug(f"Requête HTTP : {self.path}")

        if self.path == "/":
            try:
                with open("chat.html", "r", encoding="utf-8") as file:
                    body = file.read().encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as error:
                log_error(f"Erreur lecture chat.html : {error}")
                self._send_json(500, {
                    "success": False,
                    "message": str(error),
                })
                return

        log_warn(f"Endpoint inconnu : {self.path}")
        self._send_json(404, {
            "success": False,
            "message": "Endpoint not found",
        })

    def log_message(self, format, *args):
        log_debug(f"HTTP {self.address_string()} - {format % args}")

    def _send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ChatTCPServer(TCPServer):
    allow_reuse_address = True


def start_server(host="127.0.0.1", port=8520):
    global _server, _server_thread

    if _server is not None:
        log_warn("MILODO chat server already running")
        return _server

    _server = ChatTCPServer((host, int(port)), ChatRequestHandler)
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()

    log_info(f"Chat démarré sur http://{host}:{port}")
    return _server


def stop_server():
    global _server, _server_thread

    if _server is None:
        log_warn("MILODO chat server not running")
        return {
            "success": True,
            "message": "Server was not running",
        }

    _server.shutdown()
    _server.server_close()

    if _server_thread is not None:
        _server_thread.join(timeout=5)

    _server = None
    _server_thread = None

    log_info("Chat arrêté")
    return {
        "success": True,
        "message": "Server stopped",
    }


def handle_chat(message):
    preview = str(message)[:50].replace("\n", " ")
    log_info(f"Message reçu : {preview}...")
    chat_response = None
    auto_prompt = None
    intent = None
    action = None

    # Intent detection
    try:
        from skills.intent_detector import detect_intent
        intent = detect_intent(message)
        if intent and intent.get("confidence", 0) > 0.3:
            log_info(f"Intent détectée : {intent['intent']} (confiance: {intent['confidence']})")
            auto_prompt = intent["prompt"]
    except Exception as e:
        log_warn(f"Intent detection error: {e}")

    learn_match = re.match(r"^\s*(Apprends à|Apprends-moi à)\s+(.+?)\s*$", str(message), re.IGNORECASE)

    if learn_match:
        log_info("[AUTO-SKILL] Demande détectée")
        description = auto_prompt if auto_prompt else learn_match.group(2)
        name = _skill_name_from_description(description)

        log_debug("[AUTO-SKILL] Génération code")
        code = generate_code(
            "Crée uniquement le code Python d'une skill MILODO minimale. "
            "Le code doit définir une fonction run(input_data=None) qui retourne un dictionnaire structuré. "
            f"Objectif de la skill: {description}"
        )

        log_debug("[AUTO-SKILL] Création skill")
        result = create_skill(name, description, code)

        if result.get("success"):
            log_info(f"Skill auto-créé : {name}")
            return {
                "success": True,
                "message": message,
                "response": f"✅ Skill '{name}' créé et chargé.\nTu peux maintenant me demander : {description}",
            }

        log_error(f"Erreur création skill : {result.get('error')}")
        return {
            "success": False,
            "message": message,
            "response": f"❌ Erreur création skill : {result.get('error')}",
        }

    # Auto-exécution si intent détectée
    skill_result = None
    if auto_prompt and intent:
        try:
            skill_name = intent.get("skill")
            action = intent.get("default_action", "generate_report")
            if skill_name:
                log_info(f"Exécution skill : {skill_name} -> {action}")
                import importlib
                skill_module = importlib.import_module(f"skills.{skill_name}")
                if hasattr(skill_module, 'run'):
                    project = intent.get("project", "")
                    theme_path = PROJECT_PATHS.get(project)
                    skill_result = skill_module.run(
                        action=action,
                        theme_path=theme_path
                    )
                    log_info(f"Skill result : {skill_result}")
        except Exception as e:
            log_error(f"Erreur exécution skill : {e}")

    # Report dry-run (avant le report générique)
    if skill_result and action == "dry_run":
        previews = skill_result.get("previews", [])
        summary = skill_result.get("summary", {})

        if previews:
            report_lines = []
            report_lines.append(f"Mode: DRY-RUN (aucune modification)")
            report_lines.append(f"Apercu - {len(previews)} modifications proposees")
            report_lines.append(f"[HIGH confidence] {summary.get('high_confidence', 0)} [MEDIUM] {summary.get('medium_confidence', 0)}")
            report_lines.append(f"Fichiers concernes : {summary.get('files_affected', 0)}")
            report_lines.append("")

            for p in previews[:5]:
                report_lines.append(f"- [{p['estimated_risk']}] {p['description'][:70]}")
                report_lines.append(f"  File: {p['file']} | Confidence: {p['confidence']:.0%}")
                report_lines.append(f"  Fix: {p['fix_suggestion'][:80]}")
                report_lines.append("")

            report_lines.append("Pour appliquer, tape : applique les corrections")
            chat_response = "\n".join(report_lines)

    # Si skill_result contient un rapport, préparer la réponse
    if not chat_response and skill_result and isinstance(skill_result, dict):
        issues = skill_result.get("issues", [])
        summary = skill_result.get("summary", {})

        if issues:
            report_lines = []
            report_lines.append(f"Audit termine - {summary.get('total', 0)} problemes detectes")
            report_lines.append(f"[CRITICAL] {summary.get('critical', 0)} [MEDIUM] {summary.get('medium', 0)} [LOW] {summary.get('low', 0)}")
            report_lines.append("")
            report_lines.append("Top problemes :")

            for issue in issues[:5]:
                report_lines.append(f"- [{issue['severity']}] {issue['description'][:80]} ({issue['file']})")

            report_lines.append(f"Fichiers scannes : {skill_result.get('files_scanned', 0)}")
            chat_response = "\n".join(report_lines)

    fallback_response = "MILODO chat server running"

    return {
        "success": True,
        "message": message,
        "response": chat_response if chat_response else fallback_response,
    }


def _skill_name_from_description(description):
    raw_text = str(description)

    explicit_match = re.search(r"\b([A-Za-z0-9_-]+)\.py\b", raw_text)

    if explicit_match:
        text = explicit_match.group(1)
    else:
        skill_match = re.search(r"\bskill\s+([A-Za-z0-9_ -]+)", raw_text, re.IGNORECASE)

        if skill_match:
            text = skill_match.group(1)
            text = re.split(r"\s+(?:dans|pour|avec|qui|que|sur)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
        else:
            stop_words = {
                "a", "à", "de", "des", "du", "le", "la", "les", "un", "une",
                "dans", "pour", "avec", "qui", "que", "sur", "créer", "creer",
                "faire", "skill"
            }
            words = re.findall(r"[A-Za-zÀ-ÿ0-9_]+", raw_text.lower())
            meaningful = [word for word in words if word not in stop_words]
            text = "_".join(meaningful[:4])

    text = text.lower()
    text = text.replace("à", "a").replace("â", "a").replace("ä", "a")
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    text = text.replace("î", "i").replace("ï", "i")
    text = text.replace("ô", "o").replace("ö", "o")
    text = text.replace("ù", "u").replace("û", "u").replace("ü", "u")
    text = text.replace("ç", "c")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    text = text[:40].strip("_")

    if not text:
        return "auto_skill"

    if text[0].isdigit():
        text = f"skill_{text}"

    return text


if __name__ == "__main__":
    start_server()

    try:
        if _server_thread is not None:
            _server_thread.join()
    except KeyboardInterrupt:
        stop_server()
