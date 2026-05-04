export function v20Layer(state, eventBus, swarm) {
  // déclencheur de stress système
  if (state.resources < 70) {
    eventBus.emit("RESOURCE_DROP", { type: "RESOURCE_DROP" });
  }

  // surplus d’énergie
  if (state.resources > 90) {
    eventBus.emit("RESOURCE_BOOST", { type: "RESOURCE_BOOST" });
  }

  return swarm.tick();
}