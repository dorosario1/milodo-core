"""
TESTS COMPLETS POUR INTELLIGENCE.PY
Vérifie tous les cas d'usage sans nécessiter Ollama/OpenAI
"""

import unittest
import sys
from io import StringIO
from contextlib import redirect_stdout

# Importer le module à tester
from intelligence import HybridIntelligence, ai_plan, get_stats


class TestIntelligenceModule(unittest.TestCase):

    def setUp(self):
        """Avant chaque test, crée une instance propre"""
        self.intel = HybridIntelligence()

    def test_fallback_detection_shopify(self):
        """Test 1: Fallback détecte 'shopify'"""
        result = self.intel.fallback("optimiser mon store shopify")
        self.assertIn("shopify", result)
        self.assertIn("optimize store", result)

    def test_fallback_detection_marketing(self):
        """Test 2: Fallback détecte 'marketing'"""
        result = self.intel.fallback("lancer une campagne marketing")
        self.assertIn("marketing", result)
        self.assertIn("launch campaign", result)

    def test_fallback_detection_web(self):
        """Test 3: Fallback détecte 'site web'"""
        result = self.intel.fallback("créer un site web")
        self.assertIn("web", result)
        self.assertIn("create landing", result)

    def test_fallback_detection_blog(self):
        """Test 4: Fallback détecte 'blog'"""
        result = self.intel.fallback("écrire un article de blog")
        self.assertIn("content", result)
        self.assertIn("write blog", result)

    def test_fallback_default(self):
        """Test 5: Fallback par défaut"""
        result = self.intel.fallback("commande inconnue xyz123")
        self.assertIn("general", result)
        self.assertIn("analyze", result)

    def test_ai_plan_fallback(self):
        """Test 6: ai_plan utilise le fallback quand pas d'API"""
        result = ai_plan("optimiser produit shopify")
        self.assertEqual(result.get("intent"), "shopify")
        self.assertEqual(result.get("_engine"), "fallback")

    def test_is_complex_detection(self):
        """Test 7: Détection des requêtes complexes"""
        self.assertTrue(self.intel.is_complex("stratégie marketing avancée"))
        self.assertTrue(self.intel.is_complex("analyse marché prévision"))
        self.assertFalse(self.intel.is_complex("optimiser produit"))

    def test_stats_tracking(self):
        """Test 8: Les stats sont incrémentées"""
        stats_before = self.intel.stats.copy()
        self.intel.fallback("test")
        stats_after = self.intel.stats
        self.assertEqual(stats_after["fallback"], stats_before["fallback"] + 1)

    def test_parse_json_extraction(self):
        """Test 9: Extraction du JSON dans la réponse"""
        raw = '{"intent": "test", "command": "run"}'
        parsed = self.intel._parse(raw, "test_engine")
        self.assertEqual(parsed.get("intent"), "test")
        self.assertEqual(parsed.get("_engine"), "test_engine")

    def test_parse_malformed_json(self):
        """Test 10: Gère le JSON mal formé"""
        raw = "ceci n'est pas du JSON"
        parsed = self.intel._parse(raw, "fallback")
        self.assertEqual(parsed.get("intent"), "general")
        self.assertIn("_raw", parsed)

    def test_decide_without_apis(self):
        """Test 11: decide retourne toujours une décision"""
        result = self.intel.decide("optimiser shopify")
        self.assertIsNotNone(result)
        self.assertIn("intent", result)
        self.assertIn("_engine", result)

    def test_stats_print_function(self):
        """Test 12: get_stats() s'exécute sans erreur"""
        f = StringIO()
        with redirect_stdout(f):
            get_stats()
        output = f.getvalue()
        self.assertIn("Intelligence Stats", output)


class TestAgentIntegration(unittest.TestCase):
    """Tests pour l'intégration avec agent.py"""

    def test_ai_plan_returns_dict(self):
        """Test 13: ai_plan retourne un dictionnaire"""
        result = ai_plan("test goal")
        self.assertIsInstance(result, dict)

    def test_ai_plan_has_required_keys(self):
        """Test 14: ai_plan contient les clés requises"""
        result = ai_plan("shopify store")
        required_keys = ["intent", "command", "confidence", "safe", "_engine"]
        for key in required_keys:
            self.assertIn(key, result)

    def test_ai_plan_confidence_range(self):
        """Test 15: La confiance est entre 0 et 1"""
        result = ai_plan("anything")
        confidence = result.get("confidence", 0)
        self.assertGreaterEqual(confidence, 0)
        self.assertLessEqual(confidence, 1)

    def test_ai_plan_safe_flag(self):
        """Test 16: safe flag est un booléen"""
        result = ai_plan("anything")
        self.assertIsInstance(result.get("safe"), bool)


if __name__ == "__main__":
    # Exécuter les tests
    print("\n LANCEMENT DES TESTS D'INTELLIGENCE.PY")
    print("=" * 50)

    # Lancer les tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIntelligenceModule)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAgentIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("TOUS LES TESTS ONT RÉUSSI !")
        print(f"   {result.testsRun} tests passés")
    else:
        print(f"{len(result.failures)} échecs")

    sys.exit(0 if result.wasSuccessful() else 1)
