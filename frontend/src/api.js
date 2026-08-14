const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchExamples() {
  const res = await fetch(`${API_BASE}/examples`);
  if (!res.ok) throw new Error(`Failed to fetch examples: ${res.status}`);
  return res.json();
}

export async function analyzeChange({ scenarioId, changeDescription, diff }) {
  const body = {
    change_description: changeDescription,
  };
  if (scenarioId) body.scenario_id = scenarioId;
  if (diff) body.diff = diff;

  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Analysis failed: ${res.status}`);
  }
  return res.json();
}

export async function runSandbox({ scenarioId, diff, nodeMap, testCommand }) {
  const body = {
    diff,
    node_map: nodeMap,
  };
  if (scenarioId) body.scenario_id = scenarioId;
  if (testCommand) body.test_command = testCommand;

  const res = await fetch(`${API_BASE}/run-sandbox`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Sandbox run failed: ${res.status}`);
  }
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}
