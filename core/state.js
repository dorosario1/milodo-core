export const state = {
  cycle: 0,
  resources: 120,

  agents: [
    {
      id: "A1",
      energy: 100,
      type: "GATHERER",
      position: 10,
      memory: [],
      update(event) {
        if (event) {
          this.memory.push(event);
          if (this.memory.length > 5) this.memory.shift();
        }
      }
    },
    {
      id: "A2",
      energy: 100,
      type: "HUNTER",
      position: 50,
      memory: [],
      update(event) {
        if (event) {
          this.memory.push(event);
          if (this.memory.length > 5) this.memory.shift();
        }
      }
    },
    {
      id: "A3",
      energy: 100,
      type: "GATHERER",
      position: 80,
      memory: [],
      update(event) {
        if (event) {
          this.memory.push(event);
          if (this.memory.length > 5) this.memory.shift();
        }
      }
    }
  ]
};