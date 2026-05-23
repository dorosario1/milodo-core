from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .runtime_context import SCHEMA_VERSION, RuntimeContext


@dataclass
class EventPipeline:
    context: RuntimeContext
    events: list[dict[str, Any]] = field(default_factory=list)

    def collect(self, pattern: str) -> list[dict[str, Any]]:
        if pattern == "routing_priority":
            event = self._routing_priority_event()
            self.events.append(event)
            return self.events
        if pattern == "service_health":
            event = self._service_health_event()
            self.events.append(event)
            return self.events
        if pattern != "resource_exhaustion":
            return []
        event = self._docker_resource_event() if self.context.runtime == "docker" else self._synthetic_event()
        self.events.append(event)
        return self.events

    def _docker_resource_event(self) -> dict[str, Any]:
        result = self.context.run_docker_read(["stats", "--no-stream", "--format", "{{json .}}"])
        if result.returncode != 0 or not result.stdout.strip():
            return self._synthetic_event(result.stderr.strip() or "no docker stats available")
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "runtime_sample",
            "runtime": "docker",
            "source": "docker stats",
            "severity": "warning",
            "signals": {
                "memory_pressure": True,
                "cpu_pressure": False,
                "raw": result.stdout.strip().splitlines()[:5],
            },
        }

    def _service_health_event(self) -> dict[str, Any]:
        details = "deterministic fallback"
        if self.context.runtime == "docker":
            result = self.context.run_docker_read(["ps", "--format", "{{json .}}"])
            details = result.stderr.strip() or result.stdout.strip() or "no docker service data available"
        elif self.context.runtime == "kubernetes":
            result = self.context.run_kubectl_read(["get", "pods"])
            details = result.stderr.strip() or result.stdout.strip() or "no kubernetes service data available"
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "service_health_sample",
            "runtime": self.context.runtime,
            "source": "service_health pattern fixture",
            "severity": "warning",
            "signals": {
                "dependency_unreachable": True,
                "failed_healthcheck": True,
                "degraded_service_health": True,
                "learned_patterns": [
                    "startup_race_condition",
                    "unhealthy_state",
                    "dependency_failure",
                ],
                "raw": details.splitlines()[:5],
            },
        }

    def _routing_priority_event(self) -> dict[str, Any]:
        details = "deterministic fallback"
        if self.context.runtime == "docker":
            result = self.context.run_docker_read(["ps", "--format", "{{json .}}"])
            details = result.stderr.strip() or result.stdout.strip() or "no docker routing data available"
        elif self.context.runtime == "kubernetes":
            result = self.context.run_kubectl_read(["get", "services"])
            details = result.stderr.strip() or result.stdout.strip() or "no kubernetes routing data available"
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "routing_priority_sample",
            "runtime": self.context.runtime,
            "source": "routing_priority pattern fixture",
            "severity": "warning",
            "signals": {
                "generic_route_priority": True,
                "traffic_capture": True,
                "intended_route_bypassed": True,
                "wrong_middleware_chain": True,
                "learned_patterns": [
                    "route_shadowing",
                    "priority_misconfiguration",
                    "middleware_order_issue",
                ],
                "raw": details.splitlines()[:5],
            },
        }

    def _synthetic_event(self, reason: str = "deterministic fallback") -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "runtime_sample",
            "runtime": self.context.runtime,
            "source": "resource_exhaustion pattern fixture",
            "severity": "warning",
            "signals": {
                "memory_pressure": True,
                "cpu_pressure": False,
                "leak_growth": True,
                "fallback_reason": reason,
            },
        }
