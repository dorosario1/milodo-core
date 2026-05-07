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

    learn_match = re.match(r"^\s*(Apprends à|Apprends-moi à)\s+(.+?)\s*$", str(message), re.IGNORECASE)

    if learn_match:
        log_info("[AUTO-SKILL] Demande détectée")
        description = learn_match.group(2).strip()
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

    return {
        "success": True,
        "message": message,
        "response": "MILODO chat server running",
    }


def _skill_name_from_description(description):
    text = str(description).lower()
    text = text.replace("à", "a").replace("â", "a").replace("ä", "a")
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e").replace("ë", "e")
    text = text.replace("î", "i").replace("ï", "i")
    text = text.replace("ô", "o").replace("ö", "o")
    text = text.replace("ù", "u").replace("û", "u").replace("ü", "u")
    text = text.replace("ç", "c")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")

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
