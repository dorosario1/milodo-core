from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

from .causal_memory import CausalMemory
from .runtime_context import SCHEMA_VERSION, RuntimeContext


DEFAULT_PATTERN_ORDER = (
    "routing_priority",
    "service_health",
    "resource_exhaustion",
)


@dataclass(frozen=True)
class RegisteredPattern:
    pattern_id: str
    metadata: dict[str, Any]
    matcher: Callable[[list[dict[str, Any]]], bool]
    extract_features: Callable[[list[dict[str, Any]]], dict[str, Any]]

    def result(self, observations: list[dict[str, Any]]) -> dict[str, Any]:
        features = self.extract_features(observations)
        result = {
            "schema_version": SCHEMA_VERSION,
            "cause": self.pattern_id,
            "confidence": self.metadata["confidence"],
            "evidence": features.get("evidence", []),
        }
        if "learned_patterns" in features:
            result["learned_patterns"] = features["learned_patterns"]
        return result


_REGISTRY: list[RegisteredPattern] = []


def load_patterns(context: RuntimeContext | None = None) -> list[RegisteredPattern]:
    context = context or RuntimeContext()
    pattern_root = context.pattern_root
    loaded: list[RegisteredPattern] = []

    for pattern_dir in _ordered_pattern_dirs(pattern_root):
        metadata_path = pattern_dir / "pattern.json"
        matcher_path = pattern_dir / "matcher.py"
        if not metadata_path.exists() or not matcher_path.exists():
            continue

        metadata = context.load_json(metadata_path)
        module = _load_matcher_module(metadata["pattern_id"], matcher_path)
        register_pattern(
            metadata,
            module.match,
            module.extract_features,
            registry=loaded,
        )

    _REGISTRY[:] = loaded
    return list(_REGISTRY)


def register_pattern(
    metadata: dict[str, Any],
    matcher: Callable[[list[dict[str, Any]]], bool],
    extract_features: Callable[[list[dict[str, Any]]], dict[str, Any]],
    registry: list[RegisteredPattern] | None = None,
) -> RegisteredPattern:
    pattern = RegisteredPattern(
        pattern_id=metadata["pattern_id"],
        metadata=metadata,
        matcher=matcher,
        extract_features=extract_features,
    )
    target = _REGISTRY if registry is None else registry
    target.append(pattern)
    return pattern


def evaluate_patterns(
    observations: list[dict[str, Any]],
    registry: Iterable[RegisteredPattern] | None = None,
    runtime_type: str = "unknown",
) -> dict[str, Any]:
    active_registry = list(registry) if registry is not None else (_REGISTRY or load_patterns())
    memory = CausalMemory()
    pattern_errors: list[dict[str, str]] = []

    for pattern in active_registry:
        try:
            if pattern.matcher(observations):
                result = pattern.result(observations)
                try:
                    memory.remember_match(
                        pattern.pattern_id,
                        result["confidence"],
                        runtime_type,
                    )
                except Exception:
                    pass
                return result
        except Exception as error:
            pattern_errors.append(
                {
                    "pattern_id": pattern.pattern_id,
                    "error": str(error),
                }
            )
            continue

    unknown_summary = summarize_unknown_signals(observations)
    try:
        memory.remember_unknown(unknown_summary, runtime_type, near_match=False)
    except Exception:
        pass

    return {
        "schema_version": SCHEMA_VERSION,
        "cause": "unknown",
        "confidence": 0.0,
        "evidence": unknown_summary.get("signals", []),
        "pattern_errors": pattern_errors,
    }


def get_pattern_metadata(
    pattern_id: str | None = None,
    registry: Iterable[RegisteredPattern] | None = None,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    active_registry = list(registry) if registry is not None else (_REGISTRY or load_patterns())
    if pattern_id is None:
        return [pattern.metadata for pattern in active_registry]
    for pattern in active_registry:
        if pattern.pattern_id == pattern_id:
            return pattern.metadata
    return None


def _ordered_pattern_dirs(pattern_root: Path) -> list[Path]:
    pattern_dirs = [path for path in pattern_root.iterdir() if path.is_dir()]
    order = {pattern_id: index for index, pattern_id in enumerate(DEFAULT_PATTERN_ORDER)}
    return sorted(
        pattern_dirs,
        key=lambda path: (order.get(path.name, len(order)), path.name),
    )


def _load_matcher_module(pattern_id: str, matcher_path: Path) -> ModuleType:
    module_name = f"_milodo_pattern_{pattern_id}"
    spec = importlib.util.spec_from_file_location(module_name, matcher_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load matcher module from {matcher_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summarize_unknown_signals(observations: list[dict[str, Any]]) -> dict[str, Any]:
    signal_frequency: dict[str, int] = {}
    for observation in observations:
        for signal, value in observation.get("signals", {}).items():
            if signal == "raw" or not value:
                continue
            signal_frequency[signal] = signal_frequency.get(signal, 0) + 1
    return {
        "features": {
            "signals": list(signal_frequency),
            "signal_frequency": signal_frequency,
        },
        "signals": list(signal_frequency),
        "signal_frequency": signal_frequency,
        "source": "event_pipeline",
    }
