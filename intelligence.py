"""
INTELLIGENCE HYBRIDE MILODO
Ollama (gratuit) + OpenAI (précis) + Fallback (manuel)
"""

import subprocess
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional

from logger import log_info, log_error, log_warn, log_debug


class HybridIntelligence:
    def __init__(self):
        self.config = self._load_config()
        log_info(f"Config chargée : provider={self.config['provider']}")
        self.ollama_available = self._check_ollama()
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code == 200:
                self.ollama_available = True
                log_info("Ollama détecté sur localhost:11434")
        except Exception:
            self.ollama_available = False
        self.openai_available = self._check_openai()
        self.stats = {"ollama": 0, "openai": 0, "fallback": 0, "errors": []}

    def __call__(self):
        return self

    def _load_config(self) -> Dict[str, Any]:
        default_config = {
            "provider": "fallback",
            "ollama": {
                "url": "http://localhost:11434",
                "model": "llama3",
            },
            "openai": {
                "model": "gpt-4o-mini",
            },
        }

        try:
            config_path = Path(__file__).resolve().parent / "config.json"

            if not config_path.exists():
                return default_config

            with config_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            ai_config = data.get("ai", {})
            openai_config = ai_config.get("openai", {})
            ollama_config = ai_config.get("ollama", {})

            config = {
                "provider": ai_config.get("provider", default_config["provider"]),
                "ollama": {
                    "url": ollama_config.get("url", default_config["ollama"]["url"]),
                    "model": ollama_config.get("model", default_config["ollama"]["model"]),
                },
                "openai": {
                    "api_key": openai_config.get("api_key", ""),
                    "model": openai_config.get("model", default_config["openai"]["model"]),
                },
            }

            # Fallback vers variable d'environnement si api_key vide
            if not config.get("openai", {}).get("api_key", ""):
                import os
                env_key = os.environ.get("OPENAI_API_KEY", "")
                if env_key:
                    config["openai"]["api_key"] = env_key
                    log_info("Clé API chargée depuis OPENAI_API_KEY")

            return config
        except Exception:
            return default_config

    def _check_ollama(self) -> bool:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def _check_openai(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def ask_ollama(self, prompt: str, model: str = None) -> Optional[str]:
        try:
            import requests

            model = model or self.config.get("ollama", {}).get("model", "llama3.2")
            url = self.config.get("ollama", {}).get("url", "http://localhost:11434")
            start_time = time.perf_counter()
            r = requests.post(
                f"{url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=300,
            )
            ms = int((time.perf_counter() - start_time) * 1000)
            log_debug(f"Réponse en {ms}ms")
            if r.status_code == 200:
                self.stats["ollama"] += 1
                return r.json().get("response", "")
        except Exception as error:
            log_error(f"Ollama error: {error}")
            self.stats["errors"].append(str(error))
        return None

    def ask_openai(self, prompt: str, model: str = None) -> Optional[str]:
        if not self.openai_available:
            return None
        try:
            import openai

            model = model or self.config["openai"]["model"]
            openai.api_key = os.getenv("OPENAI_API_KEY") or self.config["openai"].get("api_key", "")
            start_time = time.perf_counter()
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            ms = int((time.perf_counter() - start_time) * 1000)
            log_debug(f"Réponse en {ms}ms")
            self.stats["openai"] += 1
            return response.choices[0].message.content
        except Exception as error:
            log_error(f"OpenAI error: {error}")
            self.stats["errors"].append(str(error))
        return None

    def fallback(self, prompt: str) -> str:
        self.stats["fallback"] += 1
        p = prompt.lower()
        if "shopify" in p or "produit" in p or "store" in p:
            return '{"intent": "shopify", "command": "optimize store", "confidence": 0.7, "safe": true}'
        if "marketing" in p or "campagne" in p or "pub" in p:
            return '{"intent": "marketing", "command": "launch campaign", "confidence": 0.7, "safe": true}'
        if "site" in p or "web" in p or "landing" in p:
            return '{"intent": "web", "command": "create landing", "confidence": 0.7, "safe": true}'
        if "blog" in p or "article" in p:
            return '{"intent": "content", "command": "write blog", "confidence": 0.7, "safe": true}'
        return '{"intent": "general", "command": "analyze", "confidence": 0.5, "safe": true}'

    def is_complex(self, prompt: str) -> bool:
        keywords = ["stratégie", "analyse marché", "prévision", "scoring", "complex", "multi-step"]
        return any(k in prompt.lower() for k in keywords)

    def decide(self, prompt: str, force_openai: bool = False) -> Dict[str, Any]:
        if force_openai or self.is_complex(prompt):
            result = self.ask_openai(prompt)
            if result:
                log_info(f"Provider utilisé : openai")
                return self._parse(result, "openai")
        provider = self.config["provider"]
        if provider == "fallback":
            log_info(f"Provider utilisé : fallback")
            return self._parse(self.fallback(prompt), "fallback")
        if provider == "openai":
            result = self.ask_openai(prompt)
            if result:
                log_info(f"Provider utilisé : openai")
                return self._parse(result, "openai")
            log_warn("Fallback activé - provider principal échoué")
            log_info(f"Provider utilisé : fallback")
            return self._parse(self.fallback(prompt), "fallback")
        if self.config.get("provider") == "ollama" and self.ollama_available:
            response = self.ask_ollama(prompt)

            if response:
                log_info(f"Provider utilisé : ollama")
                return self._parse(response, "ollama")
        if provider == "ollama":
            log_warn("Fallback activé - provider principal échoué")
            log_info(f"Provider utilisé : fallback")
            return self._parse(self.fallback(prompt), "fallback")
        if self.ollama_available:
            result = self.ask_ollama(prompt)
            if result:
                log_info(f"Provider utilisé : ollama")
                return self._parse(result, "ollama")
        if self.openai_available:
            response = self.ask_openai(prompt)

            if response:
                log_info(f"Provider utilisé : openai")
                return self._parse(response, "openai")
        log_info(f"Provider utilisé : fallback")
        return self._parse(self.fallback(prompt), "fallback")

    def _parse(self, raw: str, engine: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                data["_engine"] = engine
                return data
        except Exception:
            pass
        return {
            "intent": "general",
            "command": "analyze",
            "confidence": 0.5,
            "_engine": engine,
            "_raw": raw[:200],
        }

    def get_stats(self) -> Dict:
        return self.stats


# Instance unique
hybrid = HybridIntelligence()


def ai_plan(goal: str) -> dict:
    prompt = f"""Objectif: "{goal}"
Réponds UNIQUEMENT au format JSON:
{{"intent": "type (shopify/marketing/web/general)", "command": "commande", "confidence": 0.0-1.0, "safe": true/false}}"""
    return hybrid.decide(prompt)


def get_stats():
    stats = hybrid.get_stats()
    log_info("\n Intelligence Stats:")
    log_info(f"  Ollama: {stats['ollama']} appels")
    log_info(f"  OpenAI: {stats['openai']} appels")
    log_info(f"  Fallback: {stats['fallback']} appels")
    if stats["errors"]:
        log_error(f"  Erreurs: {stats['errors'][-2:]}")
