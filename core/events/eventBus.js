export class EventBus {
  constructor() {
    this.listeners = new Map();
  }

  on(event, fn) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(fn);
  }

  emit(event, data) {
    const handlers = this.listeners.get(event);
    if (!handlers) return;

    for (const fn of handlers) {
      fn(data);
    }
  }
}