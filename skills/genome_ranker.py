import json
import math
import re
from pathlib import Path
from itertools import combinations


GENES = (
    "sticky_nav",
    "gradient_bg",
    "hero_video",
    "hero_cta",
    "dark_theme",
    "animation_heavy",
    "minimal_header",
    "clean_layout",
    "schema_org",
    "og_complete",
    "responsive_images",
    "lazy_load",
    "faq_section",
    "pricing_table",
    "testimonials",
)


def load_generations(genome_dir="genome_evo") -> list[dict]:
    """
    Parse genome_evo/gen_*/index.html and optional metadata.
    """
    root = Path(genome_dir)
    generations = []

    if not root.exists():
        return generations

    for gen_dir in sorted(root.glob("gen_*"), key=_generation_sort_key):
        if not gen_dir.is_dir():
            continue

        html_path = gen_dir / "index.html"
        if not html_path.exists():
            continue

        html = html_path.read_text(encoding="utf-8", errors="replace")
        metadata = _load_metadata(gen_dir)
        genes = extract_genes_from_html(html)
        score = _extract_score(metadata, html, genes)
        sections = _extract_sections(html, score)

        generations.append({
            "generation": _parse_generation_number(gen_dir.name),
            "score": score,
            "sections": sections,
            "genes": genes,
        })

    return generations


def extract_genes_from_html(html: str) -> dict[str, bool]:
    """
    Detect 15 boolean UI/evolution genes from HTML.
    """
    lower = html.lower()

    return {
        "sticky_nav": bool(re.search(r"position\s*:\s*(sticky|fixed)", lower))
        and ("nav" in lower or "header" in lower),
        "gradient_bg": "gradient(" in lower
        or "linear-gradient" in lower
        or "radial-gradient" in lower,
        "hero_video": "<video" in lower
        or "hero-video" in lower
        or re.search(r'class=["\'][^"\']*hero[^"\']*["\'][^>]*>.*?<video', lower, re.DOTALL) is not None,
        "hero_cta": ("hero" in lower and _has_cta(lower)),
        "dark_theme": _detect_dark_theme(lower),
        "animation_heavy": _count_occurrences(lower, ("animation", "@keyframes", "transition", "animate__")) >= 5,
        "minimal_header": _detect_minimal_header(lower),
        "clean_layout": _detect_clean_layout(lower),
        "schema_org": "schema.org" in lower
        or 'application/ld+json' in lower,
        "og_complete": all(
            token in lower
            for token in ("og:title", "og:description", "og:url")
        ),
        "responsive_images": bool(re.search(r"<img[^>]+(srcset|sizes)=", lower)),
        "lazy_load": 'loading="lazy"' in lower
        or "loading='lazy'" in lower,
        "faq_section": "faq" in lower
        or "frequently asked" in lower
        or "questions fréquentes" in lower,
        "pricing_table": "pricing" in lower
        or "price-table" in lower
        or "tarif" in lower
        or "forfait" in lower,
        "testimonials": "testimonial" in lower
        or "témoignage" in lower
        or "temoignage" in lower
        or "avis client" in lower
        or "reviews" in lower,
    }


def compute_gene_scores(generations: list[dict]) -> dict[str, dict]:
    """
    Compute average score impact for each gene.
    """
    scores = {}

    for gene in GENES:
        with_scores = [
            g["score"]
            for g in generations
            if g.get("genes", {}).get(gene)
        ]
        without_scores = [
            g["score"]
            for g in generations
            if not g.get("genes", {}).get(gene)
        ]

        avg_with = _average(with_scores)
        avg_without = _average(without_scores)
        impact = avg_with - avg_without if with_scores and without_scores else 0.0

        scores[gene] = {
            "avg_score_with": round(avg_with, 4),
            "avg_score_without": round(avg_without, 4),
            "impact": round(impact, 4),
            "occurrences": len(with_scores),
        }

    return scores


def compute_gene_stability(generations: list[dict]) -> dict[str, float]:
    """
    Normalized score variance when gene is present. 0=chaotic, 1=stable.
    """
    stability = {}

    for gene in GENES:
        values = [
            g["score"]
            for g in generations
            if g.get("genes", {}).get(gene)
        ]

        if len(values) < 2:
            stability[gene] = 0.0
            continue

        variance = _variance(values)
        normalized = max(0.0, 1.0 - min(variance / 2500.0, 1.0))
        stability[gene] = round(normalized, 4)

    return stability


def detect_correlations(generations: list[dict], min_occurrences=5) -> list[dict]:
    """
    Detect gene pairs whose combined effect differs from individual effects.
    """
    gene_scores = compute_gene_scores(generations)
    correlations = []

    for gene_a, gene_b in combinations(GENES, 2):
        with_pair = [
            g["score"]
            for g in generations
            if (
                g.get("genes", {}).get(gene_a)
                and g.get("genes", {}).get(gene_b)
            )
        ]

        if len(with_pair) < min_occurrences:
            continue

        without_pair = [
            g["score"]
            for g in generations
            if not (
                g.get("genes", {}).get(gene_a)
                and g.get("genes", {}).get(gene_b)
            )
        ]

        if not without_pair:
            continue

        combined_impact = _average(with_pair) - _average(without_pair)
        expected = (
            gene_scores[gene_a]["impact"]
            + gene_scores[gene_b]["impact"]
        )
        synergy = combined_impact - expected

        correlations.append({
            "genes": [gene_a, gene_b],
            "occurrences": len(with_pair),
            "combined_impact": round(combined_impact, 4),
            "expected_impact": round(expected, 4),
            "synergy": round(synergy, 4),
            "type": "positive" if synergy >= 0 else "negative",
        })

    correlations.sort(key=lambda item: abs(item["synergy"]), reverse=True)
    return correlations


def rank_genes(genome_dir="genome_evo", min_occurrences=5) -> dict:
    """
    Main ranking function.
    """
    generations = load_generations(genome_dir)
    gene_scores = compute_gene_scores(generations)
    stability = compute_gene_stability(generations)

    ranked = []
    for gene, data in gene_scores.items():
        if data["occurrences"] < min_occurrences:
            continue

        rank = _compute_rank(data["impact"], stability.get(gene, 0.0))
        ranked.append({
            "gene": gene,
            "avg_score_with": data["avg_score_with"],
            "avg_score_without": data["avg_score_without"],
            "impact": data["impact"],
            "stability": stability.get(gene, 0.0),
            "rank": round(rank, 4),
            "occurrences": data["occurrences"],
        })

    top_positive = sorted(
        [item for item in ranked if item["rank"] > 0],
        key=lambda item: item["rank"],
        reverse=True,
    )
    top_negative = sorted(
        [item for item in ranked if item["rank"] < 0],
        key=lambda item: abs(item["rank"]),
        reverse=True,
    )
    most_stable = sorted(
        ranked,
        key=lambda item: item["stability"],
        reverse=True,
    )
    most_unstable = sorted(
        ranked,
        key=lambda item: item["stability"],
    )

    rankings = {
        "generations_analyzed": len(generations),
        "genes_detected": len(GENES),
        "min_occurrences": min_occurrences,
        "top_positive": top_positive,
        "top_negative": top_negative,
        "most_stable": most_stable,
        "most_unstable": most_unstable,
        "correlations": detect_correlations(
            generations,
            min_occurrences=min_occurrences,
        ),
        "export_path": "",
    }
    rankings["export_path"] = export_rankings(rankings)
    return rankings


def export_rankings(rankings: dict) -> str:
    """
    Save rankings to .milodo/rankings.json.
    """
    output_path = Path(".milodo/rankings.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rankings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(output_path)


def _compute_rank(impact, stability):
    return impact * stability


def _load_metadata(gen_dir: Path) -> dict:
    for name in (
        "metadata.json",
        "metrics.json",
        "score.json",
        "report.json",
        "analysis.json",
    ):
        path = gen_dir / name
        if not path.exists():
            continue

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    return {}


def _extract_score(metadata: dict, html: str, genes: dict[str, bool]) -> float:
    score = _find_numeric_score(metadata)
    if score is not None:
        return round(float(score), 4)

    base = 45.0
    weights = {
        "hero_cta": 8,
        "clean_layout": 7,
        "schema_org": 7,
        "og_complete": 6,
        "responsive_images": 5,
        "lazy_load": 4,
        "testimonials": 4,
        "faq_section": 3,
        "pricing_table": 3,
        "minimal_header": 3,
        "sticky_nav": 2,
        "gradient_bg": 1,
        "dark_theme": 1,
        "hero_video": -2,
        "animation_heavy": -4,
    }

    for gene, active in genes.items():
        if active:
            base += weights.get(gene, 0)

    lower = html.lower()
    if "<title>" in lower:
        base += 4
    if '<meta name="description"' in lower or "name='description'" in lower:
        base += 4
    if "<h1" in lower:
        base += 4
    if re.search(r"<img[^>]+alt=[\"'][^\"']+", lower):
        base += 4

    return round(max(0.0, min(100.0, base)), 4)


def _find_numeric_score(value):
    if isinstance(value, (int, float)):
        return value

    if isinstance(value, dict):
        for key in (
            "score",
            "global_score",
            "overall_score",
            "fitness",
            "quality_score",
        ):
            score = value.get(key)
            if isinstance(score, (int, float)):
                return score

        for nested in value.values():
            score = _find_numeric_score(nested)
            if score is not None:
                return score

    if isinstance(value, list):
        for item in value:
            score = _find_numeric_score(item)
            if score is not None:
                return score

    return None


def _extract_sections(html: str, score: float) -> dict:
    sections = {}

    for name in ("nav", "hero", "header", "main", "footer"):
        match = re.search(
            rf"<[^>]*(?:id|class)=['\"][^'\"]*{name}[^'\"]*['\"][^>]*>.*?</[^>]+>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        section_html = match.group(0) if match else ""
        sections[name] = {
            "score": score if section_html else 0.0,
            "html": section_html,
        }

    return sections


def _generation_sort_key(path: Path):
    return _parse_generation_number(path.name)


def _parse_generation_number(name: str) -> int:
    match = re.search(r"gen_(\d+)", name)
    return int(match.group(1)) if match else 0


def _average(values):
    return sum(values) / len(values) if values else 0.0


def _variance(values):
    avg = _average(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


def _count_occurrences(text: str, tokens: tuple[str, ...]) -> int:
    return sum(text.count(token) for token in tokens)


def _has_cta(lower_html: str) -> bool:
    return bool(re.search(
        r"(buy now|shop now|commander|acheter|réserver|reserver|contact|devis|cta|button|btn)",
        lower_html,
    ))


def _detect_dark_theme(lower_html: str) -> bool:
    dark_tokens = (
        "#000",
        "#111",
        "#121212",
        "#0d1117",
        "background: black",
        "background-color: black",
        "dark-theme",
    )
    return any(token in lower_html for token in dark_tokens)


def _detect_minimal_header(lower_html: str) -> bool:
    header_match = re.search(
        r"<header[^>]*>(.*?)</header>",
        lower_html,
        re.DOTALL,
    )
    if not header_match:
        return False

    header = header_match.group(1)
    link_count = len(re.findall(r"<a\b", header))
    return 0 < link_count <= 5


def _detect_clean_layout(lower_html: str) -> bool:
    semantic_tags = sum(
        lower_html.count(tag)
        for tag in ("<header", "<main", "<section", "<footer")
    )
    nested_divs = lower_html.count("<div")
    return semantic_tags >= 3 and nested_divs < 80
