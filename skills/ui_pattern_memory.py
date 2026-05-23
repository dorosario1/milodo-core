from __future__ import annotations

from typing import Any

from skills.knowledge_capture import capture_fix_pattern, recommend_known_fix


def save_ui_pattern(
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
        domain="ui",
        signals=signals,
        source_project=source_project,
    )


def recommend_ui_fix(input_text: str) -> dict[str, Any]:
    return recommend_known_fix(input_text, domain="ui")

