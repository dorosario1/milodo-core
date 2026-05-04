import { emit } from "../core/events.js";

const THRESHOLDS = {
  LOW_RESOURCES: 80,
  CRITICAL_RESOURCES: 40,
  ANOMALY: 1
};

export function v10(state) {

  const r = state.metrics.resources;
  const a = state.metrics.anomalies;

  if (r <= THRESHOLDS.LOW_RESOURCES && r > THRESHOLDS.CRITICAL_RESOURCES) {
    emit("LOW_RESOURCES", { value: r, level: "warning" });
  }

  if (r <= THRESHOLDS.CRITICAL_RESOURCES) {
    emit("CRITICAL_RESOURCES", { value: r, level: "critical" });
  }

  if (a >= THRESHOLDS.ANOMALY) {
    emit("ANOMALY_DETECTED", { count: a });
  }

  return state;
}