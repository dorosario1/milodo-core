import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.causal_engine import CausalEngine
from core.causal_benchmark import CausalBenchmark
from core.event_pipeline import EventPipeline
from core.runtime_context import RuntimeContext, healthcheck
from core.runtime_transfer_validator import RuntimeTransferValidator
from core.soak_persistence import (
    graceful_shutdown,
    resume_previous_soak,
    rotate_old_reports,
    save_soak_report,
)
from core.soak_long_term import (
    compare_snapshot_drift,
    detect_long_term_regression,
    generate_long_term_report,
    save_runtime_snapshot,
)
from core.soak_runner import SoakRunner
from core.strategy_engine import StrategyEngine
from core.validation_engine import ValidationEngine
from memory.causal_memory import CausalMemory


class ValidationEngineTest(unittest.TestCase):
    def test_healthcheck_ok(self):
        self.assertEqual(healthcheck()["status"], "ok")

    def test_resource_exhaustion_validation_pipeline(self):
        context = RuntimeContext(runtime="docker")
        events = EventPipeline(context).collect("resource_exhaustion")
        causal = CausalEngine(context).identify(events)
        strategy = StrategyEngine(context).apply(causal)
        validation = ValidationEngine(context).validate(strategy)

        self.assertEqual(causal["cause"], "resource_exhaustion")
        self.assertEqual(strategy["strategy"], "fix_memory_leak")
        self.assertTrue(strategy["rollback_available"])
        self.assertTrue(validation["stable"])
        self.assertTrue(validation["rollback_available"])

    def test_service_health_validation_pipeline(self):
        context = RuntimeContext(runtime="docker")
        events = EventPipeline(context).collect("service_health")
        causal = CausalEngine(context).identify(events)
        strategy = StrategyEngine(context).apply(causal)
        validation = ValidationEngine(context).validate(strategy)

        self.assertEqual(causal["cause"], "service_health")
        self.assertIn(strategy["strategy"], {"dependency_wait", "health_watchdog"})
        self.assertIn("startup_race_condition", causal["learned_patterns"])
        self.assertIn("unhealthy_state", causal["learned_patterns"])
        self.assertIn("dependency_failure", causal["learned_patterns"])
        self.assertTrue(strategy["rollback_available"])
        self.assertTrue(validation["stable"])
        self.assertTrue(validation["rollback_available"])

    def test_routing_priority_validation_pipeline(self):
        context = RuntimeContext(runtime="docker")
        events = EventPipeline(context).collect("routing_priority")
        causal = CausalEngine(context).identify(events)
        strategy = StrategyEngine(context).apply(causal)
        validation = ValidationEngine(context).validate(strategy)

        self.assertEqual(causal["cause"], "routing_priority")
        self.assertEqual(strategy["strategy"], "priority_explicit")
        self.assertIn("route_shadowing", causal["learned_patterns"])
        self.assertIn("priority_misconfiguration", causal["learned_patterns"])
        self.assertIn("middleware_order_issue", causal["learned_patterns"])
        self.assertTrue(strategy["rollback_available"])
        self.assertTrue(validation["stable"])
        self.assertTrue(validation["rollback_available"])

    def test_causal_memory_tracks_history_scores_and_rollback(self):
        path = Path("memory") / "causal_memory_test.json"
        if path.exists():
            path.unlink()
        try:
            memory = CausalMemory(path)
            memory.persist_execution(
                {
                    "schema_version": "1.0",
                    "runtime": "docker",
                    "causal_engine": {"cause": "routing_priority"},
                    "strategy_engine": {
                        "pattern": "routing_priority",
                        "strategy": "priority_explicit",
                        "applied": True,
                        "rollback_strategy": {
                            "name": "restore_implicit_priority",
                            "available": True,
                        },
                    },
                    "validation_engine": {
                        "stable": True,
                        "rollback_available": True,
                    },
                }
            )

            data = memory.read()
            self.assertEqual(memory.get_pattern_frequency("routing_priority"), 1)
            self.assertEqual(
                memory.get_strategy_success_rate("routing_priority", "priority_explicit"),
                1.0,
            )
            self.assertEqual(memory.get_runtime_success_rate("routing_priority", "docker"), 1.0)
            self.assertEqual(
                memory.get_best_strategy("routing_priority", "docker"),
                "priority_explicit",
            )
            self.assertEqual(data["stability_scores"]["routing_priority"]["stable"], 1)
            self.assertEqual(data["rollback_history"][0]["strategy"], "priority_explicit")
        finally:
            if path.exists():
                path.unlink()

    def test_causal_memory_recovers_corrupted_json(self):
        path = Path("memory") / "causal_memory_corrupt_test.json"
        if path.exists():
            path.unlink()
        try:
            path.write_text("{not-json", encoding="utf-8")
            memory = CausalMemory(path)
            data = memory.read()

            self.assertEqual(data["schema_version"], "1.0")
            self.assertEqual(data["records"], [])
            self.assertTrue(list(path.parent.glob(path.name + ".corrupt.*")))
        finally:
            if path.exists():
                path.unlink()
            for corrupt in path.parent.glob(path.name + ".corrupt.*"):
                corrupt.unlink()

    def test_causal_memory_accepts_concurrent_writes(self):
        path = Path("memory") / "causal_memory_concurrent_test.json"
        if path.exists():
            path.unlink()

        def write_once(index):
            CausalMemory(path).persist_execution(
                {
                    "schema_version": "1.0",
                    "runtime": "docker",
                    "causal_engine": {"cause": "service_health"},
                    "strategy_engine": {
                        "pattern": "service_health",
                        "strategy": "dependency_wait",
                        "applied": True,
                        "rollback_strategy": {"name": f"rollback_{index}", "available": True},
                    },
                    "validation_engine": {"stable": True, "rollback_available": True},
                }
            )

        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                list(executor.map(write_once, range(3)))

            memory = CausalMemory(path)
            self.assertEqual(memory.get_pattern_frequency("service_health"), 3)
            self.assertEqual(memory.get_strategy_success_rate("service_health", "dependency_wait"), 1.0)
            self.assertEqual(len(memory.read()["rollback_history"]), 3)
        finally:
            if path.exists():
                path.unlink()
            lock_path = path.with_suffix(path.suffix + ".lock")
            if lock_path.exists():
                lock_path.unlink()

    def test_runtime_transfer_validator_reuses_strategy(self):
        path = Path("memory") / "causal_memory_transfer_test.json"
        if path.exists():
            path.unlink()

        def record(runtime):
            return {
                "schema_version": "1.0",
                "runtime": runtime,
                "causal_engine": {"cause": "service_health"},
                "strategy_engine": {
                    "pattern": "service_health",
                    "strategy": "dependency_wait",
                    "applied": True,
                    "rollback_strategy": {
                        "name": "restore_previous_health_policy",
                        "available": True,
                    },
                },
                "validation_engine": {"stable": True, "rollback_available": True},
            }

        try:
            memory = CausalMemory(path)
            memory.persist_execution(record("docker"))
            memory.persist_execution(record("kubernetes"))

            validator = RuntimeTransferValidator(memory)
            result = validator.validate_transferability(
                "service_health",
                "docker",
                "kubernetes",
            )

            self.assertTrue(result["transferable"])
            self.assertEqual(result["strategy"], "dependency_wait")
            self.assertEqual(result["runtime_compatibility"]["docker"], 1.0)
            self.assertEqual(result["runtime_compatibility"]["kubernetes"], 1.0)
            self.assertGreaterEqual(result["confidence"], 0.9)
        finally:
            if path.exists():
                path.unlink()
            lock_path = path.with_suffix(path.suffix + ".lock")
            if lock_path.exists():
                lock_path.unlink()

    def test_causal_benchmark_ranks_runtime_strategy_and_transfer(self):
        path = Path("memory") / "causal_memory_benchmark_test.json"
        if path.exists():
            path.unlink()

        def record(runtime, strategy="dependency_wait", stable=True):
            return {
                "schema_version": "1.0",
                "runtime": runtime,
                "causal_engine": {"cause": "service_health"},
                "strategy_engine": {
                    "pattern": "service_health",
                    "strategy": strategy,
                    "applied": True,
                    "rollback_strategy": {
                        "name": "restore_previous_health_policy",
                        "available": True,
                    },
                },
                "validation_engine": {"stable": stable, "rollback_available": True},
            }

        try:
            memory = CausalMemory(path)
            memory.persist_execution(record("docker"))
            memory.persist_execution(record("docker"))
            memory.persist_execution(record("kubernetes"))

            benchmark = CausalBenchmark(memory)
            pattern = benchmark.benchmark_pattern("service_health")
            runtime = benchmark.benchmark_runtime("docker")
            strategies = benchmark.benchmark_strategy("service_health")
            transfers = benchmark.rank_transferability("service_health")

            self.assertEqual(pattern["best_runtime"], "docker")
            self.assertEqual(pattern["best_strategy"], "dependency_wait")
            self.assertEqual(pattern["runtime_reliability"]["docker"], 1.0)
            self.assertEqual(pattern["runtime_reliability"]["kubernetes"], 1.0)
            self.assertEqual(pattern["stability_score"], 1.0)
            self.assertEqual(strategies[0]["strategy"], "dependency_wait")
            self.assertTrue(transfers[0]["transferable"])
            self.assertGreaterEqual(transfers[0]["confidence"], 0.9)
            self.assertEqual(runtime["reliability"], 1.0)
        finally:
            if path.exists():
                path.unlink()
            lock_path = path.with_suffix(path.suffix + ".lock")
            if lock_path.exists():
                lock_path.unlink()

    def test_soak_runner_reports_stability(self):
        path = Path("memory") / "causal_memory_soak_test.json"
        if path.exists():
            path.unlink()
        try:
            memory = CausalMemory(path)
            runner = SoakRunner(
                patterns=["service_health"],
                runtimes=["docker", "kubernetes"],
                memory=memory,
            )
            report = runner.run_soak_test(interval=0.0, max_cycles=2)

            self.assertEqual(report["cycles"], 2)
            self.assertTrue(report["stable"])
            self.assertFalse(report["memory_growth_detected"])
            self.assertFalse(report["strategy_regression"])
            self.assertFalse(report["corruption_detected"])
            self.assertGreaterEqual(report["transfer_consistency"], 0.9)
            self.assertEqual(memory.get_pattern_frequency("service_health"), 4)
        finally:
            if path.exists():
                path.unlink()
            lock_path = path.with_suffix(path.suffix + ".lock")
            if lock_path.exists():
                lock_path.unlink()

    def test_soak_report_persistence_rotation_resume_and_shutdown(self):
        reports_dir = Path("reports") / "soak" / "test_runtime"
        reports_dir.mkdir(parents=True, exist_ok=True)

        def cleanup():
            for path in reports_dir.glob("*"):
                path.unlink()
            reports_dir.rmdir()

        try:
            for index in range(3):
                save_soak_report(
                    {
                        "schema_version": "1.0",
                        "cycles": index + 1,
                        "stable": True,
                        "memory_growth_detected": False,
                        "strategy_regression": False,
                        "transfer_consistency": 1.0,
                        "corruption_detected": False,
                    },
                    reports_dir,
                )

            rotated = rotate_old_reports(reports_dir, keep=2)
            resumed = resume_previous_soak(reports_dir)
            runner = SoakRunner(patterns=["service_health"], runtimes=["docker"])
            shutdown = graceful_shutdown(
                runner,
                {"schema_version": "1.0", "cycles": resumed["next_cycle"], "stable": True},
                reports_dir,
            )

            self.assertEqual(len(rotated), 1)
            self.assertTrue(resumed["resumable"])
            self.assertEqual(resumed["next_cycle"], 4)
            self.assertTrue(shutdown["stopped"])
            self.assertTrue(shutdown["interrupted"])
            self.assertTrue(runner.stop_requested)
            self.assertTrue((reports_dir / "latest_state.json").exists())
        finally:
            cleanup()

    def test_long_term_soak_snapshots_and_report(self):
        memory_path = Path("memory") / "causal_memory_long_term_test.json"
        reports_dir = Path("reports") / "soak" / "long_term_test"
        snapshots_dir = reports_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        def record(runtime):
            return {
                "schema_version": "1.0",
                "runtime": runtime,
                "causal_engine": {"cause": "service_health"},
                "strategy_engine": {
                    "pattern": "service_health",
                    "strategy": "dependency_wait",
                    "applied": True,
                    "rollback_strategy": {
                        "name": "restore_previous_health_policy",
                        "available": True,
                    },
                },
                "validation_engine": {"stable": True, "rollback_available": True},
            }

        def cleanup():
            if memory_path.exists():
                memory_path.unlink()
            lock_path = memory_path.with_suffix(memory_path.suffix + ".lock")
            if lock_path.exists():
                lock_path.unlink()
            for path in snapshots_dir.glob("*"):
                path.unlink()
            if (reports_dir / "long_term_report.json").exists():
                (reports_dir / "long_term_report.json").unlink()
            snapshots_dir.rmdir()
            for path in reports_dir.glob("*"):
                if path.is_file():
                    path.unlink()
            reports_dir.rmdir()

        try:
            memory = CausalMemory(memory_path)
            memory.persist_execution(record("docker"))
            memory.persist_execution(record("kubernetes"))
            first = save_runtime_snapshot(reports_dir, memory, ["service_health"])
            memory.persist_execution(record("docker"))
            second = save_runtime_snapshot(reports_dir, memory, ["service_health"])

            drift = compare_snapshot_drift(first, second, memory_growth_ratio=10.0)
            regression = detect_long_term_regression(snapshots_dir)
            report = generate_long_term_report(reports_dir)

            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertFalse(drift["memory_drift_detected"])
            self.assertFalse(drift["benchmark_regression"])
            self.assertFalse(drift["strategy_instability"])
            self.assertFalse(drift["corruption_detected"])
            self.assertFalse(regression["regression_detected"])
            self.assertTrue(report["stable"])
            self.assertTrue((reports_dir / "long_term_report.json").exists())
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
