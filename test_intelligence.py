import os
import sys
import time


PROMPT = "Réponds uniquement 'OK' en français"


def main():
    _configure_utf8_console()

    audit = {
        "import_ok": False,
        "import_error": "",
        "ollama": False,
        "openai": False,
        "fallback": False,
        "providers": [],
        "generation_ok": False,
        "generation_ms": 0,
        "generation_provider": "None",
        "generation_response": "",
        "generation_error": "",
        "fallback_ok": False,
        "fallback_path": "",
        "fallback_provider": "",
        "fallback_error": "",
    }

    try:
        import intelligence

        audit["import_ok"] = True
    except Exception as error:
        audit["import_error"] = str(error)
        _print_report(audit)
        return 1

    hybrid = intelligence.hybrid

    audit["ollama"] = bool(getattr(hybrid, "ollama_available", False))
    audit["openai"] = bool(os.getenv("OPENAI_API_KEY"))
    audit["fallback"] = callable(getattr(hybrid, "fallback", None))

    if audit["ollama"]:
        audit["providers"].append("Ollama")

    if audit["openai"]:
        audit["providers"].append("OpenAI")

    if audit["fallback"]:
        audit["providers"].append("Fallback")

    _run_generation_test(hybrid, audit)
    _run_fallback_test(hybrid, audit)
    _print_report(audit)

    return 0 if _verdict_ok(audit) else 1


def _run_generation_test(hybrid, audit):
    start = time.perf_counter()

    try:
        response = None
        provider = "None"

        if audit["ollama"]:
            response = hybrid.ask_ollama(PROMPT)
            provider = "Ollama" if response else "Ollama indisponible"

        if not response and audit["openai"]:
            response = hybrid.ask_openai(PROMPT)
            provider = "OpenAI" if response else "OpenAI indisponible"

        if not response and audit["fallback"]:
            response = hybrid.fallback(PROMPT)
            provider = "Fallback"

        elapsed = int((time.perf_counter() - start) * 1000)

        audit["generation_ms"] = elapsed
        audit["generation_provider"] = provider
        audit["generation_response"] = str(response or "").strip()
        audit["generation_ok"] = bool(audit["generation_response"])

        if not audit["generation_ok"]:
            audit["generation_error"] = "Réponse vide"
    except Exception as error:
        audit["generation_ms"] = int((time.perf_counter() - start) * 1000)
        audit["generation_error"] = str(error)
        audit["generation_ok"] = False


def _run_fallback_test(hybrid, audit):
    original_ollama = getattr(hybrid, "ollama_available", False)
    original_openai = getattr(hybrid, "openai_available", False)

    try:
        hybrid.ollama_available = False
        hybrid.openai_available = False
        result = hybrid.decide("test fallback provider")
        provider = result.get("_engine", "")

        audit["fallback_provider"] = provider
        audit["fallback_ok"] = provider == "fallback"
        audit["fallback_path"] = _provider_path(original_ollama, original_openai, provider)

        if not audit["fallback_ok"]:
            audit["fallback_error"] = f"Provider final inattendu: {provider}"
    except Exception as error:
        audit["fallback_error"] = str(error)
        audit["fallback_ok"] = False
    finally:
        hybrid.ollama_available = original_ollama
        hybrid.openai_available = original_openai


def _provider_path(ollama_available, openai_available, final_provider):
    path = []

    if ollama_available:
        path.append("Ollama")
    elif openai_available:
        path.append("OpenAI")
    else:
        path.append("Provider principal indisponible")

    path.append(str(final_provider or "inconnu").title())
    return " → ".join(path)


def _print_report(audit):
    generation_status = "✅ OK" if audit["generation_ok"] else "❌ Échec"
    fallback_status = "✅ Fonctionnel" if audit["fallback_ok"] else "❌ Échec"
    verdict = "✅ intelligence.py opérationnel" if _verdict_ok(audit) else "❌ intelligence.py nécessite diagnostic"

    print("====================================")
    print("AUDIT INTELLIGENCE MILODO")
    print("====================================")
    print(f"Import intelligence.py : {_icon(audit['import_ok'])}")

    if audit["import_error"]:
        print(f"Erreur import : {audit['import_error']}")

    print(f"Providers détectés : {audit['providers']}")
    print(f"Ollama : {_icon(audit['ollama'])}")
    print(f"OpenAI : {_icon(audit['openai'])}")
    print(f"Fallback : {_icon(audit['fallback'])}")
    print()
    print(f"Test génération : {generation_status} ({audit['generation_ms']}ms)")

    if audit["generation_error"]:
        print(f"Erreur génération : {audit['generation_error']}")

    print(f"Provider utilisé : {audit['generation_provider']}")
    print(f"Réponse : {audit['generation_response']!r}")
    print()
    print(f"Test fallback : {fallback_status}")

    if audit["fallback_error"]:
        print(f"Erreur fallback : {audit['fallback_error']}")

    print(f"Provider utilisé : {audit['fallback_path']}")
    print()
    print(f"VERDICT : {verdict}")
    print("====================================")


def _icon(value):
    return "✅" if value else "❌"


def _verdict_ok(audit):
    return (
        audit["import_ok"]
        and audit["fallback"]
        and audit["generation_ok"]
        and audit["fallback_ok"]
    )


def _configure_utf8_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
