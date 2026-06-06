import json
import random
from pathlib import Path

from skills.genome_ranker import GENES, extract_genes_from_html


def load_rankings(rankings_path=".milodo/rankings.json") -> dict | None:
    """
    Load existing rankings. Return None if rankings are unavailable.
    """
    path = Path(rankings_path)
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def compute_mutation_weights(rankings: dict) -> dict[str, dict]:
    """
    Convert rank = impact x stability into keep/remove/explore weights.
    """
    weights = {}

    for item in _iter_ranked_genes(rankings):
        gene = item.get("gene")
        if not gene:
            continue

        rank = float(item.get("rank", 0.0))
        stability = float(item.get("stability", 0.0))
        keep, remove, explore = _weights_from_rank(rank)

        if stability < 0.3:
            explore = 0.40
            remaining = 0.60
            total_keep_remove = keep + remove
            if total_keep_remove > 0:
                keep = remaining * (keep / total_keep_remove)
                remove = remaining * (remove / total_keep_remove)
            else:
                keep = 0.30
                remove = 0.30

        weights[gene] = {
            "keep_probability": round(keep, 4),
            "remove_probability": round(remove, 4),
            "explore_probability": round(explore, 4),
            "impact": float(item.get("impact", 0.0)),
            "stability": stability,
            "rank": rank,
        }

    return weights


def mutate_genome(
    genes: dict,
    mutation_weights: dict,
    exploration_rate=0.1,
) -> dict:
    """
    Apply weighted mutations and return mutated genes plus action log.
    """
    mutated = dict(genes)
    actions = []

    for gene, active in genes.items():
        weights = mutation_weights.get(gene)

        if not weights:
            if random.random() < exploration_rate:
                mutated[gene] = not active
                action = "explore"
            else:
                mutated[gene] = active
                action = "keep"

            actions.append({
                "gene": gene,
                "action": action,
                "reason": (
                    "absent des rankings, "
                    f"exploration_rate={exploration_rate}"
                ),
            })
            continue

        action = _choose_action(weights)

        if action == "keep":
            mutated[gene] = active
        elif action == "remove":
            mutated[gene] = False
        else:
            mutated[gene] = not active

        actions.append({
            "gene": gene,
            "action": action,
            "reason": _format_reason(weights),
        })

    return {
        "genes": mutated,
        "mutations_applied": actions,
    }


def suggest_injections(
    current_genes: dict,
    all_known_genes: list,
    rankings: dict,
    max_injections=2,
) -> list[str]:
    """
    Suggest absent positive-impact genes from historical rankings.
    """
    if not rankings:
        return []

    candidates = []
    known = set(all_known_genes)

    for item in _iter_ranked_genes(rankings):
        gene = item.get("gene")
        if not gene or gene not in known:
            continue

        if current_genes.get(gene):
            continue

        impact = float(item.get("impact", 0.0))
        rank = float(item.get("rank", 0.0))

        if impact > 0 and rank > 0:
            candidates.append({
                "gene": gene,
                "impact": impact,
                "rank": rank,
                "stability": float(item.get("stability", 0.0)),
            })

    candidates.sort(
        key=lambda item: (
            item["rank"],
            item["impact"],
            item["stability"],
        ),
        reverse=True,
    )

    return [
        item["gene"]
        for item in candidates[:max_injections]
    ]


def mutate_for_next_generation(
    current_html: str,
    genome_dir="genome_evo",
    rankings_path=".milodo/rankings.json",
    exploration_rate=0.1,
) -> dict:
    """
    Main adaptive mutation entrypoint.
    """
    del genome_dir

    rankings = load_rankings(rankings_path)
    original_genes = extract_genes_from_html(current_html)
    mutation_weights = (
        compute_mutation_weights(rankings)
        if rankings
        else {}
    )

    mutation_result = mutate_genome(
        original_genes,
        mutation_weights,
        exploration_rate=exploration_rate,
    )

    mutated_genes = mutation_result["genes"]
    mutations_applied = mutation_result["mutations_applied"]

    injections = suggest_injections(
        mutated_genes,
        list(GENES),
        rankings,
        max_injections=2,
    )

    for gene in injections[:2]:
        mutated_genes[gene] = True
        mutations_applied.append({
            "gene": gene,
            "action": "inject",
            "reason": _injection_reason(gene, rankings),
        })

    return {
        "original_genes": original_genes,
        "mutated_genes": mutated_genes,
        "mutations_applied": mutations_applied,
        "injections": injections[:2],
        "mutation_summary": _build_summary(mutations_applied),
    }


def _weights_from_rank(rank: float) -> tuple[float, float, float]:
    if rank > 2.0:
        return 0.85, 0.05, 0.10
    if rank > 1.0:
        return 0.70, 0.10, 0.20
    if rank > 0:
        return 0.50, 0.20, 0.30
    if rank > -1.0:
        return 0.30, 0.40, 0.30
    if rank > -2.0:
        return 0.10, 0.70, 0.20
    return 0.05, 0.85, 0.10


def _choose_action(weights: dict) -> str:
    roll = random.random()
    keep = weights["keep_probability"]
    remove = weights["remove_probability"]

    if roll < keep:
        return "keep"
    if roll < keep + remove:
        return "remove"
    return "explore"


def _iter_ranked_genes(rankings: dict):
    seen = set()

    for bucket in (
        "top_positive",
        "top_negative",
        "most_stable",
        "most_unstable",
    ):
        for item in rankings.get(bucket, []):
            gene = item.get("gene")
            if not gene or gene in seen:
                continue

            seen.add(gene)
            yield item


def _format_reason(weights: dict) -> str:
    impact = weights.get("impact", 0.0)
    stability = weights.get("stability", 0.0)
    rank = weights.get("rank", 0.0)
    return (
        f"impact={impact:+.2f}, "
        f"stability={stability:.2f}, "
        f"rank={rank:+.2f}"
    )


def _injection_reason(gene: str, rankings: dict | None) -> str:
    if not rankings:
        return "exploration uniforme, rankings indisponibles"

    for item in _iter_ranked_genes(rankings):
        if item.get("gene") == gene:
            return (
                "gène absent prometteur, "
                f"impact={float(item.get('impact', 0.0)):+.2f}, "
                f"stability={float(item.get('stability', 0.0)):.2f}, "
                f"rank={float(item.get('rank', 0.0)):+.2f}"
            )

    return "gène absent prometteur"


def _build_summary(mutations_applied: list[dict]) -> str:
    counts = {
        "keep": 0,
        "remove": 0,
        "explore": 0,
        "inject": 0,
    }

    for mutation in mutations_applied:
        action = mutation.get("action")
        if action in counts:
            counts[action] += 1

    return (
        f"{counts['keep']} kept, "
        f"{counts['remove']} removed, "
        f"{counts['explore']} explored, "
        f"{counts['inject']} injected"
    )
