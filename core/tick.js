import { appendFileSync, existsSync, readFileSync, writeFileSync } from "fs";
import { emit } from "./events.js";

const runId = new Date().toISOString();
const defaultConfig = {
  mutationBoost: false,
  reproductionCostFactor: 1,
  pressureFactor: 1
};
const smoothedConfig = {
  mutationFactor: 1,
  reproductionCostFactor: 1,
  pressureFactor: 1
};

function remember(agent, event) {
  if (!agent.memory) agent.memory = [];
  agent.memory.push(event);
  if (agent.memory.length > 5) agent.memory.shift();
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function lerp(oldValue, newValue, amount) {
  return oldValue + (newValue - oldValue) * amount;
}

function readConfig() {
  if (!existsSync("config.json")) return defaultConfig;

  try {
    const parsed = JSON.parse(readFileSync("config.json", "utf8"));

    return {
      mutationBoost: parsed.mutationBoost === true,
      reproductionCostFactor:
        typeof parsed.reproductionCostFactor === "number"
          ? clamp(parsed.reproductionCostFactor, 0.5, 1.5)
          : defaultConfig.reproductionCostFactor,
      pressureFactor:
        typeof parsed.pressureFactor === "number"
          ? clamp(parsed.pressureFactor, 0.75, 1.5)
          : defaultConfig.pressureFactor
    };
  } catch {
    return defaultConfig;
  }
}

function smoothConfig(config) {
  const targetMutationFactor = config.mutationBoost ? 1.45 : 1;

  smoothedConfig.mutationFactor = lerp(
    smoothedConfig.mutationFactor,
    targetMutationFactor,
    0.1
  );
  smoothedConfig.reproductionCostFactor = lerp(
    smoothedConfig.reproductionCostFactor,
    config.reproductionCostFactor,
    0.1
  );
  smoothedConfig.pressureFactor = lerp(
    smoothedConfig.pressureFactor,
    config.pressureFactor,
    0.1
  );

  return smoothedConfig;
}

function randomTrait() {
  return 0.8 + Math.random() * 0.4;
}

function ensureTraits(agent) {
  if (typeof agent.speed !== "number") agent.speed = randomTrait();
  if (typeof agent.efficiency !== "number") agent.efficiency = randomTrait();
  if (typeof agent.aggression !== "number") agent.aggression = randomTrait();
  if (typeof agent.fitnessScore !== "number") agent.fitnessScore = 0;
}

function traitDistance(a, b) {
  return (
    Math.abs(a.speed - b.speed) +
    Math.abs(a.efficiency - b.efficiency) +
    Math.abs(a.aggression - b.aggression)
  ) / 3;
}

function diversityFor(agent, agents) {
  if (agents.length <= 1) return 0.35;

  let total = 0;
  let count = 0;

  for (const other of agents) {
    if (other.id === agent.id) continue;
    total += traitDistance(agent, other);
    count++;
  }

  return count === 0 ? 0.35 : total / count;
}

function mutationStrength(agents) {
  if (agents.length <= 2) return 0.22;

  let total = 0;
  let count = 0;

  for (let i = 0; i < agents.length; i++) {
    for (let j = i + 1; j < agents.length; j++) {
      total += traitDistance(agents[i], agents[j]);
      count++;
    }
  }

  const diversity = count === 0 ? 0 : total / count;
  return diversity < 0.12 ? 0.2 : 0.12;
}

function mutateTrait(value, strength) {
  return clamp(value + (Math.random() - 0.5) * strength, 0.55, 1.55);
}

function updateFitness(agent, diversityBonus) {
  const energyFitness = agent.energy / 120;
  const traitFitness =
    agent.efficiency * 0.45 + agent.speed * 0.25 + agent.aggression * 0.15;

  agent.fitnessScore = Number((energyFitness + traitFitness + diversityBonus).toFixed(3));
}

function createDiverseAgent(id, position) {
  return {
    id,
    energy: 82,
    type: Math.random() < 0.75 ? "GATHERER" : "HUNTER",
    position,
    speed: randomTrait(),
    efficiency: randomTrait(),
    aggression: randomTrait(),
    fitnessScore: 0,
    memory: []
  };
}

function average(values) {
  if (values.length === 0) return 0;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function roundMetric(value) {
  return Number(value.toFixed(3));
}

function updateMetrics(state) {
  for (const agent of state.agents) {
    ensureTraits(agent);
  }

  const avgSpeed = roundMetric(average(state.agents.map((agent) => agent.speed)));
  const avgEfficiency = roundMetric(average(state.agents.map((agent) => agent.efficiency)));
  const avgAggression = roundMetric(average(state.agents.map((agent) => agent.aggression)));
  const bestFitness = roundMetric(
    Math.max(0, ...state.agents.map((agent) => agent.fitnessScore || 0))
  );

  state.metrics = {
    cycle: state.cycle,
    population: state.agents.length,
    avgSpeed,
    avgEfficiency,
    avgAggression,
    bestFitness
  };

  if (!Array.isArray(state.metricsHistory)) state.metricsHistory = [];
  state.metricsHistory.push(state.metrics);
  if (state.metricsHistory.length > 50) state.metricsHistory.shift();

  if (state.cycle % 50 === 0) {
    const exportPayload = {
      runId,
      data: state.metricsHistory
    };
    const serializedPayload = `${JSON.stringify(exportPayload)}\n`;

    if (existsSync("metrics.json")) {
      appendFileSync("metrics.json", serializedPayload);
    } else {
      writeFileSync("metrics.json", serializedPayload);
    }
  }

  if (state.cycle % 20 === 0) {
    console.log(
      `[MILODO V5] cycle=${state.cycle} population=${state.metrics.population} ` +
        `avgSpeed=${avgSpeed} avgEfficiency=${avgEfficiency} ` +
        `avgAggression=${avgAggression} bestFitness=${bestFitness}`
    );
  }
}

export function tick(state) {
  const config = smoothConfig(readConfig());

  state.cycle++;
  state.births = 0;
  state.deaths = 0;

  state.resources += 12;
  if (state.resources > 200) state.resources = 200;

  const survivors = [];
  const newborns = [];

  for (const agent of state.agents) {
    ensureTraits(agent);
  }

  const population = state.agents.length;
  const lowPopulation = population < 5;
  const crowdedPopulation = population >= 15;
  const mutation = mutationStrength(state.agents) * config.mutationFactor;

  for (const agent of state.agents) {
    const populationRelief = lowPopulation ? 0.45 : 0;
    const metabolism =
      (2.2 - agent.efficiency * 0.55 + agent.speed * 0.25) * config.pressureFactor -
      populationRelief;
    agent.energy -= clamp(metabolism, 1.2, 2.5);

    agent.position += (Math.random() - 0.5) * 8 * agent.speed;
    agent.position = Math.max(0, Math.min(100, agent.position));

    if (agent.type === "GATHERER" && state.resources > 30 && agent.energy < 130) {
      const gain = Math.min(3 + agent.efficiency * 2.2, state.resources - 30);
      agent.energy += gain;
      state.resources -= gain;
      agent.fitnessScore += gain * 0.05;

      remember(agent, "GATHER");
      emit("GATHER", { id: agent.id, gain });
    }

    if (agent.type === "HUNTER" && population > 3) {
      const huntingRange = 6 + agent.speed * 4 + agent.aggression * 2;
      const target = state.agents.find(
        (a) => a.id !== agent.id && Math.abs(a.position - agent.position) < huntingRange
      );

      if (
        target &&
        agent.energy > 40 &&
        Math.random() < clamp(agent.aggression * 0.45 * config.pressureFactor, 0.18, 0.82)
      ) {
        const huntGain = 5 + agent.aggression * 5;
        const huntDamage = (12 + agent.aggression * 9) * (lowPopulation ? 0.45 : 1);

        agent.energy += huntGain;
        target.energy -= huntDamage;
        agent.fitnessScore += huntGain * 0.06;

        remember(agent, "HUNT");
        remember(target, "HUNTED");

        emit("HUNT", {
          hunter: agent.id,
          target: target.id
        });
      }
    }

    if (agent.energy <= 0 || agent.energy > 170) {
      state.deaths++;
      emit("DEATH", { id: agent.id });
      continue;
    }

    const diversityBonus = clamp(diversityFor(agent, state.agents) * 0.6, 0, 0.25);
    updateFitness(agent, diversityBonus);

    const reproductionThreshold =
      128 - agent.efficiency * 12 - (lowPopulation ? 18 : 0) + (crowdedPopulation ? 18 : 0);
    const reproductionCost = (lowPopulation ? 30 : 45) * config.reproductionCostFactor;
    if (agent.energy >= reproductionThreshold && state.agents.length + newborns.length < 15) {
      agent.energy -= reproductionCost;

      const child = {
        id: `${agent.id}-${state.cycle}`,
        energy: 70,
        type:
          lowPopulation
            ? "GATHERER"
            : Math.random() < 0.2
            ? agent.type === "GATHERER"
              ? "HUNTER"
              : "GATHERER"
            : agent.type,
        position: agent.position,
        speed: mutateTrait(agent.speed, mutation),
        efficiency: mutateTrait(agent.efficiency, mutation),
        aggression: mutateTrait(agent.aggression, mutation),
        fitnessScore: 0,
        memory: []
      };

      newborns.push(child);
      state.births++;

      emit("BIRTH", {
        parent: agent.id,
        child: child.id
      });
    }

    survivors.push(agent);
  }

  state.agents = [...survivors, ...newborns];

  while (state.agents.length < 3) {
    state.agents.push(createDiverseAgent(`RESEED-${state.cycle}-${state.agents.length}`, 50));
  }

  if (state.resources < 0) state.resources = 0;

  updateMetrics(state);
}
