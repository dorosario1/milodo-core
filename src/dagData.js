export const nodes = [
  {
    id: "build",
    data: { label: "build" },
    position: { x: 0, y: 0 },
    style: {
      background: "#2563eb",
      border: "1px solid #1d4ed8",
      color: "#ffffff",
      fontWeight: 600,
      width: 120,
    },
  },
  {
    id: "test",
    data: { label: "test" },
    position: { x: 220, y: 0 },
    style: {
      background: "#f59e0b",
      border: "1px solid #d97706",
      color: "#111827",
      fontWeight: 600,
      width: 120,
    },
  },
  {
    id: "deploy",
    data: { label: "deploy" },
    position: { x: 440, y: 0 },
    style: {
      background: "#16a34a",
      border: "1px solid #15803d",
      color: "#ffffff",
      fontWeight: 600,
      width: 120,
    },
  },
];

export const edges = [
  { id: "e1", source: "build", target: "test" },
  { id: "e2", source: "test", target: "deploy" },
];
