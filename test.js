import { state } from "./core/state.js";
import { tick } from "./core/tick.js";

function runSimulation(ticks = 300) {
  let births = 0;
  let deaths = 0;
  let resourceZeroCount = 0;

  for (let i = 0; i < ticks; i++) {
    tick(state);

    births += state.births || 0;
    deaths += state.deaths || 0;

    if (state.resources <= 0) {
      resourceZeroCount++;
    }

    state.births = 0;
    state.deaths = 0;
  }

  return {
    finalPopulation: state.agents.length,
    births,
    deaths,
    resourceZeroCount
  };
}

function evaluate(result) {
  let pass = true;

  if (result.finalPopulation <= 0) {
    console.log("❌ FAIL: population extinct");
    pass = false;
  }

  if (result.births === 0) {
    console.log("❌ FAIL: no births");
    pass = false;
  }

  if (result.deaths === 0) {
    console.log("❌ FAIL: no deaths");
    pass = false;
  }

  if (result.resourceZeroCount > 50) {
    console.log("❌ FAIL: resources stuck at 0 too often");
    pass = false;
  }

  if (pass) console.log("✅ PASS: ecosystem stable");

  return pass;
}

console.log("================================");
console.log("MILODO AUTO-TEST");
console.log("================================");

const result = runSimulation(300);

console.log("\nRESULT:");
console.log(result);

evaluate(result);