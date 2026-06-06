import json
from datetime import datetime
from pathlib import Path

from skills.audit_engine import audit_html
from skills.orchestrator import run_orchestrator


REPORT_PATH = Path(".milodo/benchmark_report.json")

BASE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Chaussures</title>
    <meta name="description" content="Découvrez notre sélection de chaussures de sport pour homme et femme. Livraison rapide et retours simples.">
    <link rel="canonical" href="https://example.com/chaussures">
    <meta property="og:title" content="Chaussures">
    <meta property="og:description" content="Découvrez notre sélection de chaussures de sport.">
    <meta property="og:url" content="https://example.com/chaussures">
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Chaussures"}
    </script>
</head>
<body>
    <h1>Chaussures de sport</h1>
    <img src="shoe-1.jpg">
    <img src="shoe-2.jpg" alt="">
    <a href="/promo">Cliquez ici</a>
    <a href="/contact">Contactez-nous</a>
</body>
</html>"""


TEST_CASES = [
    {
        "name": "patch_correct",
        "original": BASE_HTML,
        "patched": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Chaussures de Sport Premium | Livraison Rapide 24h</title>
    <meta name="description" content="Découvrez notre sélection complète de chaussures de sport pour homme et femme. Livraison rapide, retours simples et conseils experts.">
    <link rel="canonical" href="https://example.com/chaussures">
    <meta property="og:title" content="Chaussures de Sport Premium">
    <meta property="og:description" content="Découvrez notre sélection complète de chaussures de sport.">
    <meta property="og:url" content="https://example.com/chaussures">
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Chaussures de Sport Premium"}
    </script>
</head>
<body>
    <h1>Chaussures de sport premium</h1>
    <img src="shoe-1.jpg" alt="Chaussure de sport bleue">
    <img src="shoe-2.jpg" alt="Chaussure de sport rouge">
    <a href="/promo">Voir les promotions chaussures</a>
    <a href="/contact">Contactez notre équipe</a>
</body>
</html>""",
        "expected_accepted": True,
        "expected_comparison": "improved",
    },
    {
        "name": "patch_degrade",
        "original": BASE_HTML,
        "patched": """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Chaussures</h1>
    <img src="shoe-1.jpg">
    <a href="/promo">ici</a>
</body>
</html>""",
        "expected_accepted": False,
        "expected_comparison": "degraded",
    },
    {
        "name": "patch_cosmetic",
        "original": BASE_HTML,
        "patched": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <!-- commentaire cosmétique -->
    <title>Chaussures</title>
    <meta name="description" content="Découvrez notre sélection de chaussures de sport pour homme et femme. Livraison rapide et retours simples.">
    <link rel="canonical" href="https://example.com/chaussures">
    <meta property="og:title" content="Chaussures">
    <meta property="og:description" content="Découvrez notre sélection de chaussures de sport.">
    <meta property="og:url" content="https://example.com/chaussures">
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Chaussures"}
    </script>
</head>
<body>
    <h1>Chaussures de sport</h1>

    <img src="shoe-1.jpg">
    <img src="shoe-2.jpg" alt="">
    <a href="/promo">Cliquez ici</a>
    <a href="/contact">Contactez-nous</a>
</body>
</html>""",
        "expected_accepted": True,
        "expected_comparison": "stable",
    },
    {
        "name": "patch_partial",
        "original": BASE_HTML,
        "patched": """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Chaussures</title>
    <meta name="description" content="Découvrez notre sélection de chaussures de sport pour homme et femme. Livraison rapide et retours simples.">
    <link rel="canonical" href="https://example.com/chaussures">
    <meta property="og:title" content="Chaussures">
    <meta property="og:description" content="Découvrez notre sélection de chaussures de sport.">
    <meta property="og:url" content="https://example.com/chaussures">
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Chaussures"}
    </script>
</head>
<body>
    <h1>Chaussures de sport</h1>
    <img src="shoe-1.jpg" alt="Chaussure de sport bleue">
    <img src="shoe-2.jpg" alt="">
    <a href="/promo">Voir les promotions</a>
    <a href="/contact">Contactez-nous</a>
</body>
</html>""",
        "expected_accepted": True,
        "expected_comparison": "improved",
    },
]


def run_benchmark():
    print("=" * 54)
    print("MILODO BENCHMARK REGRESSION — PHASE 3")
    print("=" * 54)

    cases = []
    passed = 0
    silent_regressions = 0

    for test_case in TEST_CASES:
        audit_before = audit_html(test_case["original"])
        result = run_orchestrator(
            original_html=test_case["original"],
            patched_html=test_case["patched"],
            audit_before=audit_before,
        )

        silent_regression = (
            result.get("accepted") is True
            and result.get("score_comparison") == "degraded"
        )
        silent_regressions += int(silent_regression)

        passed_case = (
            result.get("accepted") == test_case["expected_accepted"]
            and result.get("score_comparison") == test_case["expected_comparison"]
        )
        passed += int(passed_case)

        case_result = {
            "name": test_case["name"],
            "score_before": result.get("score_before"),
            "score_after": result.get("score_after"),
            "delta": result.get("score_delta"),
            "accepted": result.get("accepted"),
            "rollback_required": result.get("rollback_required"),
            "rolled_back": result.get("rolled_back"),
            "score_comparison": result.get("score_comparison"),
            "error": result.get("error"),
            "silent_regression": silent_regression,
            "passed": passed_case,
        }
        cases.append(case_result)

        print(
            f"{test_case['name']}: "
            f"accepted={case_result['accepted']} "
            f"comparison={case_result['score_comparison']} "
            f"delta={case_result['delta']} "
            f"passed={passed_case}"
        )

    total = len(TEST_CASES)
    failed = total - passed
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "silent_regressions_detected": silent_regressions,
            "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
        },
        "cases": cases,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("Résumé final")
    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Silent regressions: {silent_regressions}")
    print(f"Pass rate: {report['summary']['pass_rate']}%")

    return report


if __name__ == "__main__":
    run_benchmark()
