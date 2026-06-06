import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

@dataclass
class BenchmarkResult:
    url: str
    theme_type: str
    issues: List[Dict]
    false_positives: List[str]
    false_negatives: List[str]
    execution_time: float
    timestamp: str
class HeuristicsBenchmark:
    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.corpus_path = Path(".milodo/corpus.json")
        self.results_path = Path(".milodo/benchmark_results.json")
    def load_corpus(self) -> List[Dict]:
        """Charger corpus depuis .milodo/corpus.json"""
        if not self.corpus_path.exists():
            raise FileNotFoundError(f"Corpus introuvable: {self.corpus_path}")

        with open(self.corpus_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Transformer la structure par catégories en liste plate
        sites = []
        for category, urls in data.get("sites_par_categorie", {}).items():
            for url in urls:
                sites.append({
                    "url": url,
                    "theme_type": category,
                    "expected_issues": data.get("expected_issues", {}).get(
                        url,
                        data.get("default_expected", [])
                    ),
                    "verified": data.get("verified", False)
                })

        return sites
    def _audit_url(self, url: str) -> List[Dict]:
        """Audit une URL via audit_router pour supporter les sites distants."""
        from skills.audit_router import run
        result = run(action="audit_url", url=url)
        return result.get("issues", [])
    def run_benchmark(self, sample_size: Optional[int] = None):
        from skills.shopify_audit import ShopifyAuditor as ShopifyAudit
        corpus = self.load_corpus()
        if sample_size:
            corpus = corpus[:sample_size]
        for site in corpus:
            start = time.time()
            try:
                issues = self._audit_url(site["url"])
            except Exception as e:
                print(f"Fallback pour {site['url']}: {e}")
                audit = ShopifyAudit()
                issues = audit.detect_ui_issues(site["url"]).get("issues", [])
            exec_time = time.time() - start
            result = BenchmarkResult(
                url=site["url"],
                theme_type=site["theme_type"],
                issues=issues,
                false_positives=[],
                false_negatives=[],
                execution_time=exec_time,
                timestamp=datetime.now().isoformat(),
            )
            self.results.append(result)
        self.save_results()
    def save_results(self):
        data = [asdict(r) for r in self.results]
        self.results_path.parent.mkdir(exist_ok=True)
        with open(self.results_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    def calculate_metrics(self) -> Dict:
        issue_counts = {}
        fp_counts = {}
        for result in self.results:
            for issue in result.issues:
                issue_type = issue.get("type")
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
            for fp in result.false_positives:
                fp_counts[fp] = fp_counts.get(fp, 0) + 1
        precision = {}
        for issue_type, total in issue_counts.items():
            fp = fp_counts.get(issue_type, 0)
            precision[issue_type] = (
                round((total - fp) / total * 100, 1)
                if total > 0
                else 0
            )
        total_issues = sum(issue_counts.values())
        total_false_positives = sum(fp_counts.values())
        return {
            "precision_by_heuristic": precision,
            "total_false_positives": total_false_positives,
            "total_issues": total_issues,
            "global_precision": (
                round(
                    (total_issues - total_false_positives)
                    / total_issues
                    * 100,
                    1,
                )
                if total_issues > 0
                else 0
            ),
        }
    def generate_report(self) -> str:
        metrics = self.calculate_metrics()
        report = "# Benchmark Heuristics\n\n"
        report += f"## Global: {metrics['global_precision']}% precision\n"
        report += f"Total issues: {metrics['total_issues']}\n"
        report += f"False positives: {metrics['total_false_positives']}\n\n"
        report += "## Par heuristic\n\n"
        for h, p in sorted(
            metrics["precision_by_heuristic"].items(),
            key=lambda x: x[1],
        ):
            report += f"- {h}: {p}%\n"
        return report
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Exécuter benchmark")
    parser.add_argument("--report", action="store_true", help="Générer rapport")
    args = parser.parse_args()
    bm = HeuristicsBenchmark()
    if args.run:
        bm.run_benchmark()
    if args.report:
        print(bm.generate_report())
