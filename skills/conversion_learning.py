from __future__ import annotations

from typing import Any

from skills.knowledge_capture import capture_fix_pattern, detect_repeated_success, recommend_known_fix


def save_conversion_pattern(
    pattern_id: str,
    problem: str,
    recommended_fix: str,
    signals: list[str] | None = None,
    source_project: str = "DofitPro",
) -> dict[str, Any]:
    return capture_fix_pattern(
        pattern_id=pattern_id,
        problem=problem,
        recommended_fix=recommended_fix,
        domain="conversion",
        signals=signals,
        source_project=source_project,
    )


def save_branding_pattern(
    pattern_id: str,
    problem: str,
    recommended_fix: str,
    signals: list[str] | None = None,
    source_project: str = "DofitPro",
) -> dict[str, Any]:
    return capture_fix_pattern(
        pattern_id=pattern_id,
        problem=problem,
        recommended_fix=recommended_fix,
        domain="branding",
        signals=signals,
        source_project=source_project,
    )


def recommend_conversion_fix(input_text: str) -> dict[str, Any]:
    return recommend_known_fix(input_text, domain="conversion")


def recommend_branding_fix(input_text: str) -> dict[str, Any]:
    return recommend_known_fix(input_text, domain="branding")


def repeated_conversion_successes() -> list[dict[str, Any]]:
    return detect_repeated_success(domain="conversion", min_success=1)

