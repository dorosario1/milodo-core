import json
from pathlib import Path


def compute_maturity(rankings: dict) -> dict:
    generations = int(rankings.get("generations_analyzed", 0))
    genes = _collect_genes(rankings)
    genes_tracked = len(genes)

    if generations < 10:
        phase = "early"
    elif generations <= 30:
        phase = "growing"
    else:
        phase = "mature"

    stabilities = [
        float(gene.get("stability", 0.0))
        for gene in genes
    ]
    avg_stability = _average(stabilities)
    diversity_score = _compute_diversity_score(genes)
    convergence_risk = _compute_convergence_risk(
        genes,
        avg_stability,
        diversity_score,
    )

    return {
        "phase": phase,
        "generations_analyzed": generations,
        "genes_tracked": genes_tracked,
        "avg_stability": round(avg_stability, 4),
        "diversity_score": round(diversity_score, 4),
        "convergence_risk": round(convergence_risk, 4),
    }


def compute_exploration_rate(maturity: dict, base_rate=0.1) -> float:
    del base_rate

    phase = maturity.get("phase", "early")
    if phase == "early":
        rate = 0.25
    elif phase == "growing":
        rate = 0.15
    else:
        rate = 0.08

    if maturity.get("diversity_score", 1.0) < 0.3:
        rate += 0.10

    if maturity.get("convergence_risk", 0.0) > 0.7:
        rate += 0.05

    return round(_clamp(rate, 0.05, 0.40), 4)


def adapt_weights(
    base_weights: dict,
    maturity: dict,
    gene_stability: float,
    gene_occurrences: int,
) -> dict:
    keep = float(base_weights.get("keep_probability", base_weights.get("keep", 0.33)))
    remove = float(base_weights.get("remove_probability", base_weights.get("remove", 0.34)))
    explore = float(base_weights.get("explore_probability", base_weights.get("explore", 0.33)))

    if gene_stability > 0.8 and gene_occurrences > 10:
        explore = max(explore, 0.05)
        if explore > 0.10:
            keep += explore - 0.10
            explore = 0.10

    if gene_occurrences < 5:
        explore += 0.05

    if maturity.get("phase") == "mature" and gene_stability > 0.8:
        keep += 0.05

    if maturity.get("convergence_risk", 0.0) > 0.7:
        explore += 0.10

    keep = _clamp(keep, 0.05, 0.90)
    explore = _clamp(explore, 0.05, 0.50)
    remove = max(0.05, remove)

    return _normalize_weights(keep, remove, explore)


def detect_stagnation_signals(rankings: dict) -> dict:
    maturity = compute_maturity(rankings)
    genes = _collect_genes(rankings)
    signals = []

    if maturity["diversity_score"] < 0.3:
        signals.append("diversity below 0.3")

    stabilities = [
        float(gene.get("stability", 0.0))
        for gene in genes
    ]
    if stabilities and _variance(stabilities) < 0.01:
        signals.append("very low stability variance")

    top_share = _top_three_rank_share(genes)
    if top_share > 0.70:
        signals.append("top genes too dominant")

    high = (
        maturity["diversity_score"] < 0.25
        or maturity["avg_stability"] > 0.90
        or top_share > 0.70
    )
    medium = (
        maturity["diversity_score"] < 0.40
        or maturity["avg_stability"] > 0.75
    )

    if high:
        risk = "high"
        action = "boost_exploration"
    elif medium:
        risk = "medium"
        action = "continue"
    else:
        risk = "low"
        action = "none"

    return {
        "stagnation_risk": risk,
        "signals": signals,
        "recommended_action": action,
    }


def get_adaptive_weights(
    rankings_path=".milodo/rankings.json",
    base_exploration_rate=0.1,
) -> dict:
    rankings = _load_rankings(rankings_path)

    if rankings is None:
        return {
            "maturity": {
                "phase": "early",
            },
            "global_exploration_rate": 0.33,
            "gene_weights": {},
            "diversity_boost_active": False,
            "convergence_warning": False,
        }

    maturity = compute_maturity(rankings)
    global_rate = compute_exploration_rate(
        maturity,
        base_rate=base_exploration_rate,
    )
    stagnation = detect_stagnation_signals(rankings)
    gene_weights = {}

    for gene in _collect_genes(rankings):
        name = gene.get("gene")
        if not name:
            continue

        base = _base_weights_from_rank(
            float(gene.get("rank", 0.0))
        )
        adapted = adapt_weights(
            base,
            maturity,
            float(gene.get("stability", 0.0)),
            int(gene.get("occurrences", 0)),
        )
        gene_weights[name] = adapted

    return {
        "maturity": maturity,
        "global_exploration_rate": global_rate,
        "gene_weights": gene_weights,
        "diversity_boost_active": maturity["diversity_score"] < 0.3,
        "convergence_warning": (
            stagnation["stagnation_risk"] == "high"
        ),
        "stagnation": stagnation,
    }


def _load_rankings(rankings_path: str) -> dict | None:
    path = Path(rankings_path)
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _collect_genes(rankings: dict) -> list[dict]:
    genes = {}

    for bucket in (
        "top_positive",
        "top_negative",
        "most_stable",
        "most_unstable",
    ):
        for item in rankings.get(bucket, []):
            name = item.get("gene")
            if not name or name in genes:
                continue
            genes[name] = item

    return list(genes.values())


def _base_weights_from_rank(rank: float) -> dict:
    if rank > 2.0:
        keep, remove, explore = 0.85, 0.05, 0.10
    elif rank > 1.0:
        keep, remove, explore = 0.70, 0.10, 0.20
    elif rank > 0:
        keep, remove, explore = 0.50, 0.20, 0.30
    elif rank > -1.0:
        keep, remove, explore = 0.30, 0.40, 0.30
    elif rank > -2.0:
        keep, remove, explore = 0.10, 0.70, 0.20
    else:
        keep, remove, explore = 0.05, 0.85, 0.10

    return {
        "keep": keep,
        "remove": remove,
        "explore": explore,
    }


def _compute_diversity_score(genes: list[dict]) -> float:
    if not genes:
        return 1.0

    impacts = [
        float(gene.get("impact", 0.0))
        for gene in genes
    ]
    ranks = [
        float(gene.get("rank", 0.0))
        for gene in genes
    ]
    positive = sum(1 for value in impacts if value > 0)
    negative = sum(1 for value in impacts if value < 0)
    sign_balance = (
        min(positive, negative) / max(positive, negative)
        if positive and negative
        else 0.0
    )

    rank_spread = min(
        (_max(ranks) - _min(ranks)) / 10.0,
        1.0,
    )
    occurrence_values = [
        float(gene.get("occurrences", 0.0))
        for gene in genes
    ]
    occurrence_spread = min(
        (_max(occurrence_values) - _min(occurrence_values)) / 20.0,
        1.0,
    )

    return _clamp(
        (sign_balance * 0.4)
        + (rank_spread * 0.4)
        + (occurrence_spread * 0.2),
        0.0,
        1.0,
    )


def _compute_convergence_risk(
    genes: list[dict],
    avg_stability: float,
    diversity_score: float,
) -> float:
    top_share = _top_three_rank_share(genes)
    risk = 0.0

    if diversity_score < 0.3:
        risk += 0.45
    elif diversity_score < 0.4:
        risk += 0.25

    if avg_stability > 0.9:
        risk += 0.35
    elif avg_stability > 0.75:
        risk += 0.20

    if top_share > 0.7:
        risk += 0.35
    elif top_share > 0.5:
        risk += 0.20

    return _clamp(risk, 0.0, 1.0)


def _top_three_rank_share(genes: list[dict]) -> float:
    rank_values = sorted(
        (
            abs(float(gene.get("rank", 0.0)))
            for gene in genes
        ),
        reverse=True,
    )
    total = sum(rank_values)
    if total <= 0:
        return 0.0

    return sum(rank_values[:3]) / total


def _normalize_weights(keep: float, remove: float, explore: float) -> dict:
    total = keep + remove + explore
    if total <= 0:
        keep, remove, explore = 0.33, 0.34, 0.33
        total = 1.0

    keep = keep / total
    remove = remove / total
    explore = explore / total

    if explore < 0.05:
        deficit = 0.05 - explore
        explore = 0.05
        if keep >= remove:
            keep = max(0.05, keep - deficit)
        else:
            remove = max(0.05, remove - deficit)

    if explore > 0.50:
        surplus = explore - 0.50
        explore = 0.50
        keep += surplus * 0.5
        remove += surplus * 0.5

    total = keep + remove + explore
    keep = _clamp(keep / total, 0.05, 0.90)
    explore = _clamp(explore / total, 0.05, 0.50)
    remove = max(0.05, 1.0 - keep - explore)

    total = keep + remove + explore
    return {
        "keep": round(keep / total, 4),
        "remove": round(remove / total, 4),
        "explore": round(explore / total, 4),
    }


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0

    avg = _average(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _min(values: list[float]) -> float:
    return min(values) if values else 0.0


def _max(values: list[float]) -> float:
    return max(values) if values else 0.0
