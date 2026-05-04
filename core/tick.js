import { emit } from "./events.js";

export function tick(state) {
  state.cycle++;

  // 🌱 régénération naturelle (CRITIQUE)
  state.resources += 1.5;
  if (state.resources > 200) state.resources = 200;

  const newAgents = [];

  for (const agent of state.agents) {

    // 🔥 consommation plus douce (évite extinction)
    agent.energy -= 3;

    // déplacement
    agent.position += (Math.random() - 0.5) * 8;
    agent.position = Math.max(0, Math.min(100, agent.position));

    // ===== GATHER =====
    if (agent.type === "GATHERER" && state.resources > 0 && agent.energy < 75) {
      const gain = Math.min(8, state.resources);
      agent.energy += gain;
      state.resources -= gain;

      emit("GATHER", { id: agent.id, gain });
      agent.update("GATHER");
    }

    // ===== HUNTER =====
    if (agent.type === "HUNTER") {
      const target = state.agents.find(
        a => a.id !== agent.id &&
        Math.abs(a.position - agent.position) < 12
      );

      if (target && agent.energy > 35) {
        agent.energy += 10;
        target.energy -= 15;

        emit("HUNT", { hunter: agent.id, target: target.id });

        agent.update("HUNT");
        target.update("HUNTED");

        if (target.energy <= 0) {
          emit("DEATH", { id: target.id });
          continue;
        }
      }
    }

    // ===== MORT =====
    if (agent.energy <= 0) {
      emit("DEATH", { id: agent.id });
      continue;
    }

    // ===== REPRODUCTION (plus stable) =====
    if (agent.energy > 95) {
      agent.energy -= 35;

      const child = {
        id: agent.id + "-" + state.cycle,
        energy: 65,
        type: Math.random() < 0.15
          ? (agent.type === "GATHERER" ? "HUNTER" : "GATHERER")
          : agent.type,
        position: agent.position,
        memory: [...agent.memory],
        update: agent.update
      };

      emit("BIRTH", { parent: agent.id, child: child.id });

      newAgents.push(child);
    }

    newAgents.push(agent);
  }

  state.agents = newAgents;

  // 🔥 sécurité anti-extinction
  if (state.agents.length === 0) {
    state.agents.push({
      id: "RESEED",
      energy: 80,
      type: "GATHERER",
      position: 50,
      memory: [],
      update: () => {}
    });
  }
}