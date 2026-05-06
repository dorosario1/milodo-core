import csv
import json
import os
from pathlib import Path


try:
    import requests
except ImportError:
    requests = None


BRANDING_FILE = Path(".milodo") / "shopify_branding.json"


def create_product(product_data):
    print("Creation produit Shopify demandee")

    try:
        product = _normalize_product(product_data)
        payload = {"product": product}

        if not _can_call_shopify():
            print("Shopify API non configuree, payload prepare uniquement")
            return {
                "success": False,
                "payload": payload,
                "error": "Shopify API non configuree ou requests indisponible",
            }

        url = _shopify_url("products.json")
        response = requests.post(
            url,
            headers=_shopify_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code in (200, 201):
            print("Produit Shopify cree")
            return {
                "success": True,
                "product": response.json().get("product", {}),
                "error": "",
            }

        print(f"Erreur creation produit Shopify: {response.status_code}")
        return {
            "success": False,
            "payload": payload,
            "error": response.text,
        }
    except Exception as error:
        print(f"Erreur create_product: {error}")
        return {
            "success": False,
            "payload": {},
            "error": str(error),
        }


def create_products_batch(products):
    print("Creation batch produits Shopify demandee")

    results = []

    if not isinstance(products, list):
        print("Batch invalide: liste attendue")
        return [{
            "success": False,
            "payload": {},
            "error": "products doit etre une liste",
        }]

    for index, product_data in enumerate(products, start=1):
        print(f"Traitement produit {index}/{len(products)}")
        results.append(create_product(product_data))

    print(f"Batch termine: {len(results)} resultat(s)")
    return results


def import_products_csv(csv_path):
    file_path = Path(csv_path)
    print(f"Import CSV produits demande: {file_path}")

    if not file_path.exists():
        print(f"CSV introuvable: {file_path}")
        return [{
            "success": False,
            "payload": {},
            "error": f"CSV introuvable: {file_path}",
        }]

    try:
        products = []

        with file_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)

            for row in reader:
                products.append({
                    "title": row.get("title", ""),
                    "body_html": row.get("body_html", row.get("description", "")),
                    "vendor": row.get("vendor", ""),
                    "product_type": row.get("product_type", row.get("type", "")),
                    "price": row.get("price", ""),
                    "sku": row.get("sku", ""),
                    "inventory_quantity": row.get("inventory_quantity", row.get("quantity", "")),
                })

        print(f"Produits lus depuis CSV: {len(products)}")
        return create_products_batch(products)
    except Exception as error:
        print(f"Erreur import CSV: {error}")
        return [{
            "success": False,
            "payload": {},
            "error": str(error),
        }]


def update_inventory(product_id, quantity):
    print(f"Mise a jour stock demandee: produit {product_id}")

    try:
        inventory_data = {
            "product_id": str(product_id),
            "quantity": int(quantity),
        }

        if not _can_call_shopify():
            print("Shopify API non configuree, stock prepare uniquement")
            return {
                "success": False,
                "inventory": inventory_data,
                "error": "Shopify API non configuree ou requests indisponible",
            }

        print("Mise a jour stock simple non executee: inventory_item_id et location_id requis")
        return {
            "success": False,
            "inventory": inventory_data,
            "error": "inventory_item_id et location_id requis pour modifier le stock Shopify",
        }
    except Exception as error:
        print(f"Erreur update_inventory: {error}")
        return {
            "success": False,
            "inventory": {},
            "error": str(error),
        }


def update_branding_settings(brand_name=None, primary_color=None, logo_url=None):
    print("Mise a jour branding demandee")

    try:
        BRANDING_FILE.parent.mkdir(parents=True, exist_ok=True)

        settings = {}

        if BRANDING_FILE.exists():
            with BRANDING_FILE.open("r", encoding="utf-8") as file:
                settings = json.load(file)

        if brand_name is not None:
            settings["brand_name"] = brand_name

        if primary_color is not None:
            settings["primary_color"] = primary_color

        if logo_url is not None:
            settings["logo_url"] = logo_url

        with BRANDING_FILE.open("w", encoding="utf-8") as file:
            json.dump(settings, file, indent=2, ensure_ascii=False)
            file.write("\n")

        print(f"Branding sauvegarde localement: {BRANDING_FILE}")
        return {
            "success": True,
            "settings": settings,
            "path": str(BRANDING_FILE),
        }
    except Exception as error:
        print(f"Erreur update_branding_settings: {error}")
        return {
            "success": False,
            "settings": {},
            "error": str(error),
        }


def _normalize_product(product_data):
    if not isinstance(product_data, dict):
        raise ValueError("product_data doit etre un dictionnaire")

    title = str(product_data.get("title", "")).strip()

    if not title:
        raise ValueError("title est obligatoire")

    product = {
        "title": title,
        "body_html": str(product_data.get("body_html", product_data.get("description", ""))),
        "vendor": str(product_data.get("vendor", "")),
        "product_type": str(product_data.get("product_type", product_data.get("type", ""))),
    }

    price = product_data.get("price")
    sku = product_data.get("sku")
    quantity = product_data.get("inventory_quantity", product_data.get("quantity"))

    variant = {}

    if price not in (None, ""):
        variant["price"] = str(price)

    if sku not in (None, ""):
        variant["sku"] = str(sku)

    if quantity not in (None, ""):
        variant["inventory_management"] = "shopify"
        variant["inventory_quantity"] = int(quantity)

    if variant:
        product["variants"] = [variant]

    return product


def _can_call_shopify():
    return bool(requests and _shop_name() and _access_token())


def _shopify_url(endpoint):
    return f"https://{_shop_name()}.myshopify.com/admin/api/2024-01/{endpoint}"


def _shopify_headers():
    return {
        "X-Shopify-Access-Token": _access_token(),
        "Content-Type": "application/json",
    }


def _shop_name():
    shop = os.getenv("SHOPIFY_SHOP_NAME", "").strip()
    return shop.replace(".myshopify.com", "")


def _access_token():
    return os.getenv("SHOPIFY_ACCESS_TOKEN", "").strip()
