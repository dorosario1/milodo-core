"""
INTELLIGENCE HYBRIDE MILODO
Ollama (gratuit) + OpenAI (précis) + Fallback (manuel)
"""

import subprocess
import json
import os
import re
from typing import Dict, Any, Optional


class HybridIntelligence:
    def __init__(self):
        self.ollama_available = self._check_ollama()
        self.openai_available = self._check_openai()
        self.stats = {"ollama": 0, "openai": 0, "fallback": 0, "errors": []}

    def _check_ollama(self) -> bool:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def _check_openai(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def ask_ollama(self, prompt: str, model: str = "llama3.2") -> Optional[str]:
        if not self.ollama_available:
            return None
        try:
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.stats["ollama"] += 1
                return result.stdout.strip()
        except Exception as e:
            self.stats["errors"].append(str(e))
        return None

    def ask_openai(self, prompt: str, model: str = "gpt-3.5-turbo") -> Optional[str]:
        if not self.openai_available:
            return None
        try:
            import openai

            openai.api_key = os.getenv("OPENAI_API_KEY")
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            self.stats["openai"] += 1
            return response.choices[0].message.content
        except Exception as e:
            self.stats["errors"].append(str(e))
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
                return self._parse(result, "openai")
        if self.ollama_available:
            result = self.ask_ollama(prompt)
            if result:
                return self._parse(result, "ollama")
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
    print("\n Intelligence Stats:")
    print(f"  Ollama: {stats['ollama']} appels")
    print(f"  OpenAI: {stats['openai']} appels")
    print(f"  Fallback: {stats['fallback']} appels")
    if stats["errors"]:
        print(f"  Erreurs: {stats['errors'][-2:]}")
