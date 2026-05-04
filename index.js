import { state } from "./core/state.js";
import { tick } from "./core/tick.js";
import { getEvents, clearEvents } from "./core/events.js";

function render() {
  console.clear();

  console.log("================================");
  console.log("MILODO CORE - OBSERVABILITY");
  console.log("================================");

  console.log(`[CYCLE ${state.cycle}]`);
  console.log(`RESOURCES: ${state.resources}`);
  console.log(`POPULATION: ${state.agents.length}`);

  console.log("\n================================");
  console.log("SWARM DEBUG");
  console.log("================================");

  for (const a of state.agents) {
    console.log(
      `${a.id} | ${a.type} | EN:${a.energy.toFixed(0)} | POS:${a.position.toFixed(1)} | MEM:${a.memory.length}`
    );
  }

  const events = getEvents();

  console.log("\n================================");
  console.log("EVENTS");
  console.log("================================");

  for (const e of events.slice(-10)) {
    console.log(e.type, e.payload);
  }

  clearEvents();
}

function loop() {
  tick(state);
  render(state);
}

setInterval(loop, 500);