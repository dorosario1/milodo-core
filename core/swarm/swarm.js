export function createAgent(id) {
  return {
    id,
    energy: 100,
    type: Math.random() > 0.5 ? "GATHERER" : "HUNTER",

    // 🧠 mémoire visible
    memory: [],

    update(event) {
      if (event) {
        this.memory.push(event);
        if (this.memory.length > 5) this.memory.shift();
      }

      // adaptation simple
      const lowEnergy = this.energy < 30;
      const stress = this.memory.filter(e => e === "RESOURCE_LOW").length;

      if (stress >= 2) this.type = "HUNTER";
      if (lowEnergy) this.type = "GATHERER";
    }
  };
}