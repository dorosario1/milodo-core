export function applyCore(state) {
  // ici uniquement logique CORE, pas de layers externes

  // exemple simple d'évolution du state
  state.cycle = (state.cycle || 0) + 1;

  state.resources = (state.resources ?? 100) - 1;

  if (!state.anomalies) state.anomalies = 0;

  return state;
}