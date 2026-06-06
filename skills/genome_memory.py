import json
import shutil
from datetime import datetime
from pathlib import Path


def archive_generation(
    generation_name,
    score,
    genes,
    html,
    genome_dir="genome_evo",
    memory_dir=".milodo/genome_memory",
) -> bool:
    """
    Archive generation only if score belongs to historical top 20%.
    """
    del genome_dir

    memory = _memory_path(memory_dir)
    archives = load_archives(memory_dir)

    if not _is_top_twenty_percent(float(score), archives):
        _update_memory_stats(memory)
        return False

    archive_dir = memory / "archives" / _safe_generation_name(generation_name)
    archive_dir.mkdir(parents=True, exist_ok=True)

    percentile = _score_percentile(float(score), archives)
    protected = _protected_genes_set(memory)

    (archive_dir / "index.html").write_text(
        html,
        encoding="utf-8",
    )
    _write_json(
        archive_dir / "genes.json",
        dict(genes),
    )
    _write_json(
        archive_dir / "metadata.json",
        {
            "generation": generation_name,
            "score": float(score),
            "archive_date": datetime.now().isoformat(),
            "percentile": percentile,
            "protected": sorted(
                gene
                for gene, active in genes.items()
                if active and gene in protected
            ),
        },
    )

    _update_memory_stats(memory)
    return True


def load_archives(memory_dir=".milodo/genome_memory") -> list[dict]:
    """
    Return archived generations sorted by score descending.
    """
    archives_root = _memory_path(memory_dir) / "archives"
    if not archives_root.exists():
        return []

    archives = []
    for archive_dir in archives_root.iterdir():
        if not archive_dir.is_dir():
            continue

        metadata_path = archive_dir / "metadata.json"
        genes_path = archive_dir / "genes.json"
        html_path = archive_dir / "index.html"

        if not metadata_path.exists() or not genes_path.exists():
            continue

        try:
            metadata = _read_json(metadata_path, {})
            genes = _read_json(genes_path, {})
        except Exception:
            continue

        archives.append({
            "generation": metadata.get("generation", archive_dir.name),
            "score": float(metadata.get("score", 0.0)),
            "genes": genes,
            "archive_date": metadata.get("archive_date"),
            "html_path": str(html_path),
        })

    archives.sort(key=lambda item: item["score"], reverse=True)
    return archives


def detect_protected_patterns(
    memory_dir=".milodo/genome_memory",
    min_generations=10,
) -> dict:
    """
    Persist genes present in top archives for min_generations.
    """
    memory = _memory_path(memory_dir)
    archives = load_archives(memory_dir)
    top_archives = _top_twenty_archives(archives)
    gene_data = {}

    for archive in top_archives:
        generation = archive["generation"]
        score = archive["score"]

        for gene, active in archive.get("genes", {}).items():
            if not active:
                continue

            data = gene_data.setdefault(gene, {
                "generations_present": 0,
                "first_seen": generation,
                "last_seen": generation,
                "scores": [],
            })
            data["generations_present"] += 1
            data["last_seen"] = generation
            data["scores"].append(score)

    protected = {}
    for gene, data in gene_data.items():
        if data["generations_present"] < min_generations:
            continue

        protected[gene] = {
            "generations_present": data["generations_present"],
            "first_seen": data["first_seen"],
            "last_seen": data["last_seen"],
            "avg_score": round(_average(data["scores"]), 4),
            "protected": True,
        }

    _write_json(
        memory / "protected_patterns.json",
        protected,
    )
    return protected


def suggest_resurrection(
    current_genes,
    current_score,
    memory_dir=".milodo/genome_memory",
    max_suggestions=2,
) -> list[dict]:
    """
    Suggest historically strong missing genes when current score drops.
    """
    archives = load_archives(memory_dir)
    if not archives:
        return []

    best_score = archives[0]["score"]
    if float(current_score) >= best_score * 0.95:
        return []

    candidates = {}
    for archive in archives:
        for gene, active in archive.get("genes", {}).items():
            if not active or current_genes.get(gene):
                continue

            data = candidates.setdefault(gene, {
                "scores": [],
                "last_seen": archive["generation"],
            })
            data["scores"].append(archive["score"])

    suggestions = []
    for gene, data in candidates.items():
        avg_score = _average(data["scores"])
        suggestions.append({
            "gene": gene,
            "last_seen": data["last_seen"],
            "historical_avg_score": round(avg_score, 4),
            "reason": (
                "absent du génome actuel et présent dans "
                "des archives performantes"
            ),
        })

    suggestions.sort(
        key=lambda item: item["historical_avg_score"],
        reverse=True,
    )
    return suggestions[:max_suggestions]


def prune_archives(
    memory_dir=".milodo/genome_memory",
    max_archives=50,
    keep_top=10,
) -> dict:
    """
    Keep top performers and remove overflow archives.
    """
    memory = _memory_path(memory_dir)
    archives = load_archives(memory_dir)
    before = len(archives)

    if before <= max_archives:
        return {
            "before": before,
            "after": before,
            "removed": 0,
            "kept_top_score": archives[0]["score"] if archives else None,
        }

    protected_names = {
        archive["generation"]
        for archive in archives[:keep_top]
    }
    overflow = archives[keep_top:]
    to_remove = overflow[: max(0, before - max_archives)]

    removed = 0
    for archive in to_remove:
        if archive["generation"] in protected_names:
            continue

        archive_dir = memory / "archives" / _safe_generation_name(
            archive["generation"]
        )
        if archive_dir.exists():
            shutil.rmtree(archive_dir)
            removed += 1

    _update_memory_stats(memory)
    after = len(load_archives(memory_dir))

    return {
        "before": before,
        "after": after,
        "removed": removed,
        "kept_top_score": archives[0]["score"] if archives else None,
    }


def detect_regression(
    current_score,
    memory_dir=".milodo/genome_memory",
    threshold=0.15,
) -> dict:
    """
    Detect score regression against best historical archive.
    """
    memory = _memory_path(memory_dir)
    archives = load_archives(memory_dir)
    score = float(current_score)
    best = archives[0]["score"] if archives else score

    drop_percent = 0.0
    if best > 0 and score < best:
        drop_percent = (best - score) / best

    if drop_percent > threshold:
        recommendation = "restore"
    elif drop_percent > 0.05:
        recommendation = "explore"
    else:
        recommendation = "continue"

    result = {
        "regression_detected": drop_percent > threshold,
        "current_score": score,
        "best_historical": best,
        "drop_percent": round(drop_percent, 4),
        "recommendation": recommendation,
    }

    log_path = memory / "regression_log.json"
    log = _read_json(log_path, [])
    log.append({
        "date": datetime.now().isoformat(),
        "current_score": score,
        "best_historical": best,
        "drop_percent": round(drop_percent, 4),
    })
    _write_json(log_path, log)

    return result


def take_memory_snapshot(
    generation_name,
    score,
    genes,
    html,
    genome_dir="genome_evo",
    memory_dir=".milodo/genome_memory",
) -> dict:
    """
    Main long-term genome memory entrypoint.
    """
    archived = archive_generation(
        generation_name,
        score,
        genes,
        html,
        genome_dir=genome_dir,
        memory_dir=memory_dir,
    )
    protected = detect_protected_patterns(memory_dir)
    resurrection = suggest_resurrection(
        genes,
        score,
        memory_dir=memory_dir,
        max_suggestions=2,
    )
    regression = detect_regression(
        score,
        memory_dir=memory_dir,
    )
    pruning = prune_archives(memory_dir)

    return {
        "archived": archived,
        "protected_patterns_updated": True,
        "resurrection_suggestions": resurrection,
        "regression_warning": regression,
        "pruning_executed": pruning["removed"] > 0,
        "memory_size": len(load_archives(memory_dir)),
        "protected_patterns": protected,
    }


def _memory_path(memory_dir: str) -> Path:
    path = Path(memory_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "archives").mkdir(parents=True, exist_ok=True)
    return path


def _safe_generation_name(name) -> str:
    return str(name).replace("/", "_").replace("\\", "_").strip() or "gen_unknown"


def _is_top_twenty_percent(score: float, archives: list[dict]) -> bool:
    if not archives:
        return True

    scores = sorted(
        [archive["score"] for archive in archives] + [score],
        reverse=True,
    )
    cutoff_count = max(1, int(len(scores) * 0.2))
    cutoff = scores[cutoff_count - 1]
    return score >= cutoff


def _score_percentile(score: float, archives: list[dict]) -> float:
    scores = [archive["score"] for archive in archives] + [score]
    if not scores:
        return 1.0

    below_or_equal = sum(1 for value in scores if value <= score)
    return round(below_or_equal / len(scores), 4)


def _top_twenty_archives(archives: list[dict]) -> list[dict]:
    if not archives:
        return []

    count = max(1, int(len(archives) * 0.2))
    return archives[:count]


def _protected_genes_set(memory: Path) -> set:
    data = _read_json(memory / "protected_patterns.json", {})
    return {
        gene
        for gene, info in data.items()
        if isinstance(info, dict) and info.get("protected")
    }


def _update_memory_stats(memory: Path) -> None:
    archives = load_archives(str(memory))
    stats = {
        "total_archives": len(archives),
        "best_score": archives[0]["score"] if archives else None,
        "oldest_gen": archives[-1]["generation"] if archives else None,
        "newest_gen": archives[0]["generation"] if archives else None,
    }
    _write_json(memory / "memory_stats.json", stats)


def _read_json(path: Path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
