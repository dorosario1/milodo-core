import unittest

from ai_planner import ai_plan


class AIPlannerTests(unittest.TestCase):
    def test_deploy(self):
        result = ai_plan("deploy")

        self.assertTrue(result["safe"])
        self.assertEqual(result["intent"], "deploy")
        self.assertIsNone(result["target"])
        self.assertEqual(result["command"], "deploy")
        self.assertGreater(result["confidence"], 0.0)
        self.assertIn("deploy", result["reason"])

    def test_build(self):
        result = ai_plan("build project")

        self.assertTrue(result["safe"])
        self.assertEqual(result["intent"], "build")
        self.assertEqual(result["command"], "build")

    def test_test(self):
        result = ai_plan("test api")

        self.assertTrue(result["safe"])
        self.assertEqual(result["intent"], "test")
        self.assertEqual(result["command"], "test")

    def test_healthcheck(self):
        result = ai_plan("healthcheck")

        self.assertTrue(result["safe"])
        self.assertEqual(result["intent"], "healthcheck")
        self.assertEqual(result["command"], "healthcheck")

    def test_unknown_input_is_unsafe(self):
        result = ai_plan("blabla")

        self.assertFalse(result["safe"])
        self.assertIsNone(result["intent"])
        self.assertIsNone(result["command"])
        self.assertEqual(result["confidence"], 0.0)

    def test_dangerous_keywords_are_unsafe(self):
        for text in ("rm -rf /", "format disk", "delete all data", "shutdown now", "wipe system"):
            result = ai_plan(text)

            self.assertFalse(result["safe"])
            self.assertIsNone(result["intent"])
            self.assertIsNone(result["command"])
            self.assertEqual(result["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
