import json
from datetime import datetime, timezone
from pathlib import Path

from logger import log_info, log_error, log_warn, log_debug


MEMORY_FILE = Path(".milodo") / "memory.json"


def load_memory():
    log_debug("Chargement memoire")

    if not MEMORY_FILE.exists():
        log_warn("Mémoire vide")
        return _default_memory()

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as file:
            memory_data = json.load(file)

        if not isinstance(memory_data, dict):
            log_error("Erreur mémoire : Format memoire invalide")
            return _default_memory()

        entries = memory_data.get("entries", [])

        if not isinstance(entries, list):
            log_error("Erreur mémoire : Format entrees memoire invalide")
            memory_data["entries"] = []

        if not memory_data["entries"]:
            log_warn("Mémoire vide")
        log_info("Mémoire chargée")
        return memory_data
    except (OSError, json.JSONDecodeError) as error:
        log_error(f"Erreur mémoire : {error}")
        return _default_memory()


def save_memory(memory_data):
    log_debug("Sauvegarde memoire")

    try:
        if not isinstance(memory_data, dict):
            raise ValueError("memory_data doit etre un dictionnaire")

        entries = memory_data.get("entries", [])

        if not isinstance(entries, list):
            raise ValueError("memory_data['entries'] doit etre une liste")

        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        with MEMORY_FILE.open("w", encoding="utf-8") as file:
            json.dump({"entries": entries}, file, indent=2, ensure_ascii=False)
            file.write("\n")

        log_debug("Mémoire sauvegardée")
        return {
            "success": True,
            "path": str(MEMORY_FILE),
            "entries_count": len(entries),
        }
    except Exception as error:
        log_error(f"Erreur mémoire : {error}")
        return {
            "success": False,
            "path": str(MEMORY_FILE),
            "error": str(error),
        }


def add_memory_entry(entry_type, content):
    log_debug(f"Entrée ajoutée : {entry_type}")

    memory_data = load_memory()
    entry = {
        "type": str(entry_type),
        "content": str(content),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    memory_data["entries"].append(entry)
    save_result = save_memory(memory_data)

    return {
        "success": save_result.get("success", False),
        "entry": entry,
        "error": save_result.get("error", ""),
    }


def get_memory_entries(entry_type=None):
    log_debug("Lecture historique memoire")

    memory_data = load_memory()
    entries = memory_data.get("entries", [])

    if entry_type is None:
        if not entries:
            log_warn("Mémoire vide")
        log_debug(f"Entrees retournees: {len(entries)}")
        return entries

    filtered = [
        entry for entry in entries
        if str(entry.get("type", "")).lower() == str(entry_type).lower()
    ]

    if not filtered:
        log_warn("Mémoire vide")
    log_debug(f"Entrees retournees pour {entry_type}: {len(filtered)}")
    return filtered


def search_memory(query):
    log_debug(f"Recherche mémoire : {query}")

    search_text = str(query).lower()
    results = []

    for entry in get_memory_entries():
        entry_type = str(entry.get("type", "")).lower()
        content = str(entry.get("content", "")).lower()

        if search_text in entry_type or search_text in content:
            results.append(entry)

    if not results:
        log_warn("Mémoire vide")
    log_debug(f"Resultats memoire: {len(results)}")
    return results


def clear_memory():
    log_debug("Reinitialisation memoire")

    result = save_memory(_default_memory())

    return {
        "success": result.get("success", False),
        "entries": [],
        "error": result.get("error", ""),
    }


def _default_memory():
    return {
        "entries": [],
    }
