let events = [];

export function emit(type, payload) {
  events.push({ type, payload });
}

export function getEvents() {
  return events;
}

export function clearEvents() {
  events = [];
}