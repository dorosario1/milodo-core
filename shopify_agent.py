import json
import os
from urllib import error, request

try:
    import requests
except ImportError:
    requests = None


SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "your-store")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_TOKEN", "your_token")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-01")
SHOPIFY_BASE_URL = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}"


def is_configured():
    return SHOPIFY_STORE != "your-store" and SHOPIFY_TOKEN != "your_token"


def shopify_headers():
    return {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }


def shopify_request(method, path, payload=None):
    url = f"{SHOPIFY_BASE_URL}{path}"
    headers = shopify_headers()

    if requests is not None:
        response = requests.request(method, url, json=payload, headers=headers, timeout=30)
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}
        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "body": body,
        }

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8")
            return {
                "success": 200 <= response.status < 300,
                "status_code": response.status,
                "body": json.loads(text) if text else {},
            }
    except error.HTTPError as response_error:
        text = response_error.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except ValueError:
            body = {"raw": text}
        return {
            "success": False,
            "status_code": response_error.code,
            "body": body,
        }


def fetch_products():
    result = shopify_request("GET", "/products.json")
    if not result["success"]:
        return {
            "success": False,
            "products": [],
            "errors": [result],
        }
    return {
        "success": True,
        "products": result["body"].get("products", []),
        "errors": [],
    }


def generate_product_copy(product):
    title = product.get("title", "")
    product_type = product.get("product_type", "")

    if "fitness" in product_type.lower():
        return {
            "title": f" {title} - Fitness Pro",
            "body_html": "<strong>Ameliore tes performances rapidement</strong>",
        }

    if "bande" in title.lower():
        return {
            "title": " Bande Elastique Pro - Resistance Max",
            "body_html": "<strong>Musculation a domicile efficace</strong>",
        }

    return {
        "title": f" {title} ameliore",
        "body_html": "<strong>Produit optimise pour conversion</strong>",
    }


def optimize_price(product):
    variants = product.get("variants") or []
    if not variants:
        return []

    variant = variants[0]
    price = float(variant.get("price", 0) or 0)
    new_price = price + 5 if price < 20 else price * 1.1
    return [{
        "id": variant.get("id"),
        "price": str(round(new_price, 2)),
    }]


def build_product_update(product):
    product_copy = generate_product_copy(product)
    payload = {
        "product": {
            "id": product.get("id"),
            "title": product_copy["title"],
            "body_html": product_copy["body_html"],
        }
    }
    variants = optimize_price(product)
    if variants:
        payload["product"]["variants"] = variants
    return payload


def update_product(product):
    product_id = product.get("id")
    if not product_id:
        return {
            "success": False,
            "product_id": None,
            "error": "missing product id",
        }

    result = shopify_request("PUT", f"/products/{product_id}.json", build_product_update(product))
    print("[AGENT] product updated:", product_id, result["status_code"])
    return {
        "success": result["success"],
        "product_id": product_id,
        "status_code": result["status_code"],
        "error": None if result["success"] else result["body"],
    }


def optimize_shopify_products():
    if not is_configured():
        print("[AGENT] Shopify not configured")
        return {
            "success": True,
            "action": "shopify_optimize",
            "files": [],
            "shopify": {
                "configured": False,
                "updated": [],
            },
            "errors": [],
        }

    products_result = fetch_products()
    if not products_result["success"]:
        return {
            "success": False,
            "action": "shopify_optimize",
            "files": [],
            "shopify": {
                "configured": True,
                "updated": [],
            },
            "errors": products_result["errors"],
        }

    updates = [update_product(product) for product in products_result["products"]]
    return {
        "success": all(update["success"] for update in updates),
        "action": "shopify_optimize",
        "files": [],
        "shopify": {
            "configured": True,
            "updated": updates,
        },
        "errors": [update for update in updates if not update["success"]],
    }
