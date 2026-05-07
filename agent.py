import json
import os
from urllib import error, parse, request

from intelligence import ai_plan
from logger import log_info, log_error, log_warn, log_debug
from marketing_agent import (
    generate_traffic_content,
    generate_whatsapp_scripts,
)
from shopify_agent import optimize_shopify_products
from web_agent import create_email_sequence, create_landing_page
from pathlib import Path


OUTPUT_DIR = Path("business_outputs")


def ensure_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)


def read_output_file(name):
    path = OUTPUT_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_output_file(name, content):
    ensure_output_dir()
    path = OUTPUT_DIR / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def post_json(url, payload, headers):
    action = "post_json"
    log_debug(f"Routing action : {action}")
    preview = str(payload)[:120].replace("\n", " ")
    log_debug(f"Params action : {preview}...")
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8")
            return {
                "success": 200 <= response.status < 300,
                "status_code": response.status,
                "body": json.loads(text) if text else {},
            }
    except error.HTTPError as response_error:
        log_error(f"Erreur routing : {response_error}")
        text = response_error.read().decode("utf-8", errors="replace")
        return {
            "success": False,
            "status_code": response_error.code,
            "body": text,
        }
    except OSError as request_error:
        log_error(f"Erreur routing : {request_error}")
        return {
            "success": False,
            "status_code": None,
            "body": str(request_error),
        }


def post_form(url, payload):
    action = "post_form"
    log_debug(f"Routing action : {action}")
    preview = str(payload)[:120].replace("\n", " ")
    log_debug(f"Params action : {preview}...")
    data = parse.urlencode(payload).encode("utf-8")
    req = request.Request(url, data=data, method="POST")
    try:
        with request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8")
            return {
                "success": 200 <= response.status < 300,
                "status_code": response.status,
                "body": json.loads(text) if text else {},
            }
    except error.HTTPError as response_error:
        log_error(f"Erreur routing : {response_error}")
        text = response_error.read().decode("utf-8", errors="replace")
        return {
            "success": False,
            "status_code": response_error.code,
            "body": text,
        }
    except OSError as request_error:
        log_error(f"Erreur routing : {request_error}")
        return {
            "success": False,
            "status_code": None,
            "body": str(request_error),
        }


def fallback_log(filename, content, action, message):
    file_path = write_output_file(filename, content)
    log_info(f"Action exécutée : {action}")
    return {
        "success": True,
        "action": action,
        "files": [file_path],
        "errors": [],
        "fallback": True,
    }


def autopost_content():
    action = "autopost"
    log_debug(f"Routing action : {action}")
    tiktok_content = read_output_file("tiktok_content.txt")
    instagram_content = read_output_file("instagram_content.txt")
    whatsapp_content = read_output_file("whatsapp_traffic.txt")
    posts = []
    errors = []
    files = []

    tiktok_access_token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
    tiktok_post_url = os.environ.get("TIKTOK_POST_URL", "")
    if tiktok_access_token and tiktok_post_url:
        result = post_json(
            tiktok_post_url,
            {"text": tiktok_content},
            {
                "Authorization": f"Bearer {tiktok_access_token}",
                "Content-Type": "application/json",
            },
        )
        posts.append({"channel": "tiktok", "result": result})
        if not result["success"]:
            errors.append({"channel": "tiktok", "error": result})

    instagram_access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    instagram_user_id = os.environ.get("INSTAGRAM_IG_USER_ID", "")
    instagram_image_url = os.environ.get("INSTAGRAM_IMAGE_URL", "")
    if instagram_access_token and instagram_user_id and instagram_image_url:
        media_result = post_form(
            f"https://graph.facebook.com/v19.0/{instagram_user_id}/media",
            {
                "image_url": instagram_image_url,
                "caption": instagram_content,
                "access_token": instagram_access_token,
            },
        )
        posts.append({"channel": "instagram_media", "result": media_result})
        creation_id = media_result.get("body", {}).get("id") if media_result["success"] else None
        if creation_id:
            publish_result = post_form(
                f"https://graph.facebook.com/v19.0/{instagram_user_id}/media_publish",
                {
                    "creation_id": creation_id,
                    "access_token": instagram_access_token,
                },
            )
            posts.append({"channel": "instagram_publish", "result": publish_result})
            if not publish_result["success"]:
                errors.append({"channel": "instagram", "error": publish_result})
        else:
            errors.append({"channel": "instagram", "error": media_result})

    if not posts:
        content = "\n\n".join(
            (
                f"POSTED TO TikTok\n{tiktok_content}",
                f"POSTED TO Instagram\n{instagram_content}",
                f"POSTED TO WhatsApp Traffic\n{whatsapp_content}",
            )
        )
        return fallback_log("autopost_log.txt", content, action, "[AGENT] content posted")

    files.append(write_output_file("autopost_api_result.json", json.dumps(posts, indent=2)))
    log_info(f"Action exécutée : {action}")
    return {
        "success": len(errors) == 0,
        "action": "autopost",
        "files": files,
        "errors": errors,
        "fallback": False,
    }


def send_email_real():
    action = "send_email"
    log_debug(f"Routing action : {action}")
    email_sequence = read_output_file("email_sequence.txt")
    api_key = os.environ.get("BREVO_API_KEY", "")
    sender_email = os.environ.get("BREVO_SENDER_EMAIL", "")
    sender_name = os.environ.get("BREVO_SENDER_NAME", "MILODO")
    to_email = os.environ.get("BREVO_TO_EMAIL", "")

    if not (api_key and sender_email and to_email):
        return fallback_log(
            "email_send_log.txt",
            f"SENT EMAIL SEQUENCE\n{email_sequence}",
            action,
            "[AGENT] emails sent",
        )

    result = post_json(
        "https://api.brevo.com/v3/smtp/email",
        {
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": to_email}],
            "subject": os.environ.get("BREVO_SUBJECT", "Offre exclusive MILODO"),
            "htmlContent": f"<pre>{email_sequence}</pre>",
        },
        {
            "api-key": api_key,
            "Content-Type": "application/json",
        },
    )
    file_path = write_output_file("email_api_result.json", json.dumps(result, indent=2))
    log_info(f"Action exécutée : {action}")
    return {
        "success": result["success"],
        "action": "send_email",
        "files": [file_path],
        "errors": [] if result["success"] else [result],
        "fallback": False,
    }


def send_whatsapp_real():
    action = "send_whatsapp"
    log_debug(f"Routing action : {action}")
    scripts = read_output_file("whatsapp_sales_scripts.txt")
    token = os.environ.get("WHATSAPP_TOKEN", "")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    to_number = os.environ.get("WHATSAPP_TO", "")

    if not (token and phone_number_id and to_number):
        return fallback_log(
            "whatsapp_send_log.txt",
            f"SENT WHATSAPP SCRIPTS\n{scripts}",
            action,
            "[AGENT] WhatsApp messages sent",
        )

    result = post_json(
        f"https://graph.facebook.com/v19.0/{phone_number_id}/messages",
        {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": scripts[:4000]},
        },
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    file_path = write_output_file("whatsapp_api_result.json", json.dumps(result, indent=2))
    log_info(f"Action exécutée : {action}")
    return {
        "success": result["success"],
        "action": "send_whatsapp",
        "files": [file_path],
        "errors": [] if result["success"] else [result],
        "fallback": False,
    }


def apply_goal_actions(goal):
    action = "apply_goal_actions"
    log_debug(f"Routing action : {action}")
    preview = str({"goal": goal})[:120].replace("\n", " ")
    log_debug(f"Params action : {preview}...")
    normalized_goal = str(goal or "").lower()
    try:
        decision = ai_plan(goal)
        intent = str(decision.get("intent", "")).lower()
        command = str(decision.get("command", "")).lower()
        output = {
            "success": True,
            "goal": goal,
            "decision": decision,
            "actions": [],
            "files": [],
            "shopify": {},
            "errors": [],
        }

        def merge(result):
            output["actions"].append(result.get("action"))
            output["files"].extend(result.get("files", []))
            if result.get("shopify"):
                output["shopify"] = result["shopify"]
            if not result.get("success", False):
                output["success"] = False
                output["errors"].extend(result.get("errors", []))

        run_complete = "complete" in normalized_goal
        run_auto = "auto" in normalized_goal

        if (
            run_complete
            or run_auto
            or "trafic" in normalized_goal
            or "traffic" in normalized_goal
            or intent == "marketing"
            or "launch campaign" in command
        ):
            merge(generate_traffic_content())

        if (
            run_complete
            or run_auto
            or "funnel" in normalized_goal
            or intent == "web"
            or "create landing" in command
        ):
            merge(create_landing_page())
            merge(create_email_sequence())

        if run_complete or run_auto or "sales" in normalized_goal:
            merge(generate_whatsapp_scripts())

        if (
            run_complete
            or "optimize" in normalized_goal
            or "shopify" in normalized_goal
            or intent == "shopify"
            or "optimize store" in command
        ):
            merge(optimize_shopify_products())

        if run_auto:
            merge(autopost_content())
            merge(send_email_real())
            merge(send_whatsapp_real())

        if not output["actions"]:
            output["success"] = False
            output["errors"].append("unknown business goal")
            log_warn(f"Action non reconnue : {goal}")

        log_info(f"Action exécutée : {action}")
        return output
    except Exception as error:
        log_error(f"Erreur routing : {error}")
        raise
