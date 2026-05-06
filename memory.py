import json
from datetime import datetime, timezone
from pathlib import Path


MEMORY_FILE = Path(".milodo") / "memory.json"


def load_memory():
    print("Chargement memoire")

    if not MEMORY_FILE.exists():
        print(f"Memoire introuvable: {MEMORY_FILE}")
        return _default_memory()

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as file:
            memory_data = json.load(file)

        if not isinstance(memory_data, dict):
            print("Format memoire invalide")
            return _default_memory()

        entries = memory_data.get("entries", [])

        if not isinstance(entries, list):
            print("Format entrees memoire invalide")
            memory_data["entries"] = []

        print(f"Memoire chargee: {len(memory_data['entries'])} entree(s)")
        return memory_data
    except (OSError, json.JSONDecodeError) as error:
        print(f"Erreur chargement memoire: {error}")
        return _default_memory()


def save_memory(memory_data):
    print("Sauvegarde memoire")

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

        print(f"Memoire sauvegardee: {MEMORY_FILE}")
        return {
            "success": True,
            "path": str(MEMORY_FILE),
            "entries_count": len(entries),
        }
    except Exception as error:
        print(f"Erreur sauvegarde memoire: {error}")
        return {
            "success": False,
            "path": str(MEMORY_FILE),
            "error": str(error),
        }


def add_memory_entry(entry_type, content):
    print(f"Ajout memoire: {entry_type}")

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
    print("Lecture historique memoire")

    memory_data = load_memory()
    entries = memory_data.get("entries", [])

    if entry_type is None:
        print(f"Entrees retournees: {len(entries)}")
        return entries

    filtered = [
        entry for entry in entries
        if str(entry.get("type", "")).lower() == str(entry_type).lower()
    ]

    print(f"Entrees retournees pour {entry_type}: {len(filtered)}")
    return filtered


def search_memory(query):
    print(f"Recherche memoire: {query}")

    search_text = str(query).lower()
    results = []

    for entry in get_memory_entries():
        entry_type = str(entry.get("type", "")).lower()
        content = str(entry.get("content", "")).lower()

        if search_text in entry_type or search_text in content:
            results.append(entry)

    print(f"Resultats memoire: {len(results)}")
    return results


def clear_memory():
    print("Reinitialisation memoire")

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
