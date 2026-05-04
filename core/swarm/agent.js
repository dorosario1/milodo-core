export class Agent {
  constructor(id) {
    this.id = id;
    this.energy = 100;
    this.state = "idle";
  }

  update(event) {
    if (!event) return;

    switch (event.type) {
      case "RESOURCE_DROP":
        this.energy -= 5;
        this.state = "seeking";
        break;

      case "RESOURCE_BOOST":
        this.energy += 8;
        this.state = "gathering";
        break;
    }

    if (this.energy <= 0) {
      this.state = "inactive";
    }
  }
}