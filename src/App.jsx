import { useEffect, useMemo, useState } from "react";
import ReactFlow, { Background, Controls, MiniMap } from "reactflow";
import "reactflow/dist/style.css";

const fitViewOptions = {
  padding: 0.35,
};

const statusStyles = {
  success: {
    background: "#16a34a",
    border: "1px solid #15803d",
    color: "#ffffff",
  },
  done: {
    background: "#16a34a",
    border: "1px solid #15803d",
    color: "#ffffff",
  },
  failed: {
    background: "#dc2626",
    border: "1px solid #b91c1c",
    color: "#ffffff",
  },
  pending: {
    background: "#94a3b8",
    border: "1px solid #64748b",
    color: "#0f172a",
  },
};

function statusIcon(status) {
  if (status === "success" || status === "done") return "✓";
  if (status === "failed") return "✗";
  return "…";
}

function buildGraph(tasks) {
  const nodes = tasks.map((task, index) => {
    const style = statusStyles[task.status] || statusStyles.pending;

    return {
      id: String(task.id),
      data: { label: task.name },
      position: { x: index * 220, y: 0 },
      style: {
        ...style,
        width: 120,
        fontWeight: 600,
      },
    };
  });

  const edges = tasks.slice(1).map((task, index) => ({
    id: `e-${tasks[index].id}-${task.id}`,
    source: String(tasks[index].id),
    target: String(task.id),
  }));

  return { nodes, edges };
}

export default function App() {
  const [state, setState] = useState({ runs: [], tasks: [] });
  const [selectedRunId, setSelectedRunId] = useState("");
  const [flowInstance, setFlowInstance] = useState(null);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let closed = false;

    function fetchState() {
      fetch("http://localhost:4000/state")
        .then((response) => {
          if (!response.ok) {
            throw new Error("state API unavailable");
          }
          return response.json();
        })
        .then((data) => {
          if (closed) return;
          setState((currentState) => {
            const currentJson = JSON.stringify(currentState);
            const nextJson = JSON.stringify(data);
            return currentJson === nextJson ? currentState : data;
          });
          setSelectedRunId((currentRunId) => {
            if (currentRunId) return currentRunId;
            const newestRun = [...(data.runs || [])].sort(
              (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0),
            )[0];
            return String(newestRun?.id || "");
          });
          setError("");
          setLoading(false);
        })
        .catch((apiError) => {
          if (closed) return;
          setError(apiError.message);
          setLoading(false);
        });
    }

    fetchState();
    const intervalId = setInterval(fetchState, 5000);
    const ws = new WebSocket("ws://localhost:4001");

    ws.onmessage = (message) => {
      try {
        JSON.parse(message.data);
        fetchState();
      } catch {
        fetchState();
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    return () => {
      closed = true;
      clearInterval(intervalId);
      ws.close();
    };
  }, []);

  const timelineRuns = useMemo(
    () =>
      [...state.runs].sort((a, b) => {
        const createdAtDiff = new Date(b.created_at || 0) - new Date(a.created_at || 0);
        return createdAtDiff || b.id - a.id;
      }),
    [state.runs],
  );
  const recentCommandRuns = useMemo(() => timelineRuns.filter((run) => run.command).slice(0, 5), [timelineRuns]);
  const mostUsedCommand = useMemo(() => {
    const counts = new Map();
    for (const run of timelineRuns) {
      if (!run.command) continue;
      counts.set(run.command, (counts.get(run.command) || 0) + 1);
    }

    let topCommand = "";
    let topCount = 0;
    for (const [command, count] of counts) {
      if (count > topCount) {
        topCommand = command;
        topCount = count;
      }
    }

    return topCount > 1 ? topCommand : "";
  }, [timelineRuns]);
  const lastCommand = recentCommandRuns[0]?.command || "";
  const lastFailedRun = useMemo(() => timelineRuns.find((run) => run.status === "failed") || null, [timelineRuns]);
  const selectedRun = useMemo(
    () => timelineRuns.find((run) => String(run.id) === selectedRunId) || timelineRuns[0] || null,
    [selectedRunId, timelineRuns],
  );
  const selectedTasks = useMemo(() => {
    if (!selectedRun) return [];
    return state.tasks
      .filter((task) => task.run_id === selectedRun.id)
      .sort((a, b) => a.id - b.id);
  }, [selectedRun, state.tasks]);
  const visibleTasks = useMemo(() => selectedTasks.slice(0, 50), [selectedTasks]);
  const selectedFailedTask = useMemo(() => visibleTasks.find((task) => task.status === "failed") || null, [visibleTasks]);
  const graph = useMemo(() => buildGraph(visibleTasks), [visibleTasks]);
  const nodes = useMemo(() => graph.nodes, [graph.nodes]);
  const edges = useMemo(() => graph.edges, [graph.edges]);

  function runCommand(command) {
    if (!command) return;
    setActionMessage(`Running: ${command}`);
    fetch("http://localhost:3000/run/ai", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": "milodo-secret",
      },
      body: JSON.stringify({ text: command }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("run request failed");
        }
        return response.json();
      })
      .then(() => {
        setActionMessage(`Triggered: ${command}`);
      })
      .catch((runError) => {
        setActionMessage(`Run failed: ${runError.message}`);
      });
  }

  useEffect(() => {
    if (!flowInstance || nodes.length === 0) return;
    window.requestAnimationFrame(() => {
      const failedNode = selectedFailedTask && nodes.find((node) => node.id === String(selectedFailedTask.id));
      if (failedNode) {
        flowInstance.setCenter(failedNode.position.x + 60, failedNode.position.y + 20, { zoom: 1.2, duration: 300 });
        return;
      }
      flowInstance.fitView(fitViewOptions);
    });
  }, [flowInstance, nodes, selectedFailedTask]);

  return (
    <main
      style={{
        width: "100vw",
        height: "100vh",
        background: "#f8fafc",
        color: "#0f172a",
        fontFamily:
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <section
        style={{
          height: "112px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 28px",
          borderBottom: "1px solid #e2e8f0",
          boxSizing: "border-box",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>MILODO DAG</h1>
          <p style={{ margin: "6px 0 0", color: "#475569" }}>
            {loading
              ? "Loading MILODO..."
              : selectedRun
                ? `Run #${selectedRun.id} · ${selectedRun.command}`
                : "No runs available"}
          </p>
          {lastCommand ? (
            <p style={{ margin: "6px 0 0", color: "#334155", fontSize: 13 }}>
              Last command: <strong>{lastCommand}</strong>
            </p>
          ) : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {selectedRun?.command ? (
            <button
              type="button"
              onClick={() => runCommand(selectedRun.command)}
              title={selectedRun.command}
              style={{
                height: 36,
                border: "1px solid #2563eb",
                borderRadius: 6,
                background: "#2563eb",
                color: "#ffffff",
                padding: "0 12px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Run again
            </button>
          ) : null}
          <div
            style={{
              padding: "8px 12px",
              borderRadius: 6,
              background:
                selectedRun?.status === "success" ? "#dcfce7" : selectedRun?.status === "failed" ? "#fee2e2" : "#f1f5f9",
              color: selectedRun?.status === "success" ? "#166534" : selectedRun?.status === "failed" ? "#991b1b" : "#475569",
              fontWeight: 700,
            }}
          >
            {selectedRun ? `${statusIcon(selectedRun.status)} ${selectedRun.status}` : "unavailable"}
          </div>
        </div>
      </section>

      {loading ? (
        <div style={{ padding: 28, color: "#475569" }}>Loading MILODO...</div>
      ) : error ? (
        <div style={{ padding: 28, color: "#991b1b" }}>API error: {error}</div>
      ) : state.runs.length === 0 ? (
        <div style={{ padding: 28, color: "#475569" }}>No runs available</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", height: "calc(100vh - 112px)" }}>
          <aside
            style={{
              borderRight: "1px solid #e2e8f0",
              padding: 20,
              background: "#ffffff",
              overflowY: "auto",
            }}
          >
            <h2 style={{ margin: "0 0 14px", fontSize: 16 }}>Quick Actions</h2>
            <div style={{ display: "grid", gap: 8, marginBottom: 20 }}>
              {recentCommandRuns.map((run) => {
                const isFrequent = run.command === mostUsedCommand;

                return (
                  <button
                    key={`quick-${run.id}`}
                    type="button"
                    onClick={() => runCommand(run.command)}
                    title={run.command}
                    style={{
                      width: "100%",
                      minHeight: 40,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 10,
                      border: "1px solid #cbd5e1",
                      borderRadius: 8,
                      background: isFrequent ? "#fef9c3" : "#f8fafc",
                      color: "#0f172a",
                      padding: "8px 10px",
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <span
                      style={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        fontWeight: 700,
                      }}
                    >
                      {run.command}
                    </span>
                    {isFrequent ? (
                      <span
                        style={{
                          flex: "0 0 auto",
                          borderRadius: 6,
                          background: "#fde68a",
                          color: "#92400e",
                          padding: "3px 6px",
                          fontSize: 11,
                          fontWeight: 800,
                        }}
                      >
                        frequent
                      </span>
                    ) : null}
                  </button>
                );
              })}
              {actionMessage ? <div style={{ color: "#475569", fontSize: 12 }}>{actionMessage}</div> : null}
            </div>

            <h2 style={{ margin: "0 0 14px", fontSize: 16 }}>Runs</h2>
            <div style={{ display: "grid", gap: 10 }}>
              {timelineRuns.map((run) => {
                const isSelected = selectedRun && run.id === selectedRun.id;
                const isSuccess = run.status === "success";
                const isFailed = run.status === "failed";
                const isLastFailure = lastFailedRun && run.id === lastFailedRun.id;

                return (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => setSelectedRunId(String(run.id))}
                    title={`${run.command || ""}\n${run.created_at || ""}`}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      border: isSelected ? "2px solid #1d4ed8" : "2px solid #e2e8f0",
                      borderLeft: `6px solid ${isSuccess ? "#16a34a" : isFailed ? "#dc2626" : "#94a3b8"}`,
                      borderRadius: 8,
                      background: isSelected ? "#dbeafe" : "#ffffff",
                      color: "#0f172a",
                      padding: 12,
                      cursor: "pointer",
                      boxShadow: isSelected ? "0 2px 8px rgba(37, 99, 235, 0.22)" : "none",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                      <strong>Run #{run.id}</strong>
                      <span
                        style={{
                          color: isSuccess ? "#166534" : isFailed ? "#991b1b" : "#475569",
                          fontWeight: 700,
                        }}
                      >
                        {statusIcon(run.status)} {run.status}
                      </span>
                    </div>
                    {isLastFailure ? (
                      <div
                        style={{
                          display: "inline-block",
                          marginTop: 8,
                          padding: "3px 7px",
                          borderRadius: 6,
                          background: "#fee2e2",
                          color: "#991b1b",
                          fontSize: 11,
                          fontWeight: 800,
                        }}
                      >
                        LAST FAILURE
                      </div>
                    ) : null}
                    <div style={{ marginTop: 8, fontWeight: 600 }}>{run.command}</div>
                    <div style={{ marginTop: 6, color: "#64748b", fontSize: 12 }}>{run.created_at}</div>
                  </button>
                );
              })}
            </div>
          </aside>

          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            fitViewOptions={fitViewOptions}
            nodesDraggable={false}
            onInit={setFlowInstance}
          >
            <Background color="#cbd5e1" gap={24} />
            <Controls />
            <MiniMap pannable zoomable />
          </ReactFlow>
        </div>
      )}
    </main>
  );
}
