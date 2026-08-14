import { useState, useCallback, useRef } from "react";
import Graph from "./components/Graph";
import NodePanel from "./components/NodePanel";
import ChangeInput from "./components/ChangeInput";
import StatusBar from "./components/StatusBar";
import Logo from "./components/Logo";
import { analyzeChange, runSandbox } from "./api";

const EMPTY_GRAPH = { nodes: [], edges: [], summary: "" };

export default function App({ onBackToLanding }) {
  const [status, setStatus] = useState("idle"); // idle | loading | ready | error
  const [graphData, setGraphData] = useState(EMPTY_GRAPH);
  const [selectedNode, setSelectedNode] = useState(null);
  const [sandboxResult, setSandboxResult] = useState(null);
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const [animating, setAnimating] = useState(false);
  const [error, setError] = useState(null);

  // Keep track of the current scenario for sandbox run
  const currentScenario = useRef({ scenarioId: null, diff: null });

  const handleAnalyze = useCallback(async ({ scenarioId, changeDescription, diff }) => {
    setStatus("loading");
    setError(null);
    setGraphData(EMPTY_GRAPH);
    setSelectedNode(null);
    setSandboxResult(null);
    currentScenario.current = { scenarioId, diff };

    try {
      const graph = await analyzeChange({ scenarioId, changeDescription, diff });
      setGraphData(graph);
      setStatus("ready");
    } catch (err) {
      setError(err.message || "Analysis failed. Check that the backend is running and OPENAI_API_KEY is set.");
      setStatus("error");
    }
  }, []);

  const handleRunSandbox = useCallback(async () => {
    const { scenarioId, diff } = currentScenario.current;
    if (!diff && !scenarioId) {
      setError("No diff available to apply. Provide a diff or select a scenario.");
      return;
    }

    setSandboxLoading(true);
    setError(null);
    setAnimating(true);

    // Build node map: node_id → file_path
    const nodeMap = {};
    graphData.nodes.forEach((n) => {
      nodeMap[n.id] = n.file_path;
    });

    try {
      const result = await runSandbox({
        scenarioId,
        diff,
        nodeMap,
      });
      setSandboxResult(result);
      setSandboxLoading(false);
      // Keep animating for 3s after results arrive
      setTimeout(() => setAnimating(false), 3000);
    } catch (err) {
      setError(err.message || "Sandbox run failed.");
      setSandboxLoading(false);
      setAnimating(false);
    }
  }, [graphData]);

  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
  }, []);

  // Find sandbox result for selected node
  const selectedNodeResult = selectedNode && sandboxResult
    ? sandboxResult.results.find((r) => r.node_id === selectedNode.id) || null
    : null;

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-brand">
          <Logo />
          <div className="brand-text">
            <span className="brand-name">Blast Radius</span>
            <span className="brand-tagline">pre-commit impact analysis</span>
          </div>
        </div>
        <div className="header-links">
          {onBackToLanding && (
            <button type="button" className="header-link header-link-btn" onClick={onBackToLanding}>
              ← Home
            </button>
          )}
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="header-link"
          >
            GitHub
          </a>
        </div>
      </header>
      <div className="header-spectrum" />

      {/* Main layout */}
      <div className="app-body">
        {/* Left sidebar */}
        <aside className="sidebar">
          <ChangeInput
            onAnalyze={handleAnalyze}
            loading={status === "loading"}
            disabled={sandboxLoading || animating}
          />

          {/* Graph summary */}
          {graphData.summary && (
            <div className="summary-box">
              <h3 className="section-label">Analysis Summary</h3>
              <p className="summary-text">{graphData.summary}</p>
            </div>
          )}

          {/* Legend */}
          {graphData.nodes.length > 0 && (
            <div className="legend">
              <h3 className="section-label">Risk Legend</h3>
              <div className="legend-items">
                {[
                  { risk: "will_break", color: "#ee5257", label: "Will Break" },
                  { risk: "might_break", color: "#f0a63e", label: "Might Break" },
                  { risk: "review", color: "#4fa6f2", label: "Worth Reviewing" },
                  { risk: "safe", color: "#34c17e", label: "Safe" },
                  { risk: "change", color: "#9b8cf0", label: "Proposed Change" },
                ].map(({ risk, color, label }) => {
                  const count = graphData.nodes.filter((n) => n.risk === risk).length;
                  if (count === 0) return null;
                  return (
                    <div key={risk} className="legend-item">
                      <span className="legend-dot" style={{ background: color }} />
                      <span className="legend-label">{label}</span>
                      <span className="legend-count">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </aside>

        {/* Graph area */}
        <main className="graph-area">
          <Graph
            graphData={graphData}
            sandboxResults={sandboxResult?.results || null}
            onNodeClick={handleNodeClick}
            animating={animating}
          />

          {/* Node panel overlay */}
          {selectedNode && (
            <div className="node-panel-overlay">
              <NodePanel
                node={selectedNode}
                sandboxResult={selectedNodeResult}
                onClose={() => setSelectedNode(null)}
              />
            </div>
          )}
        </main>
      </div>

      {/* Status bar */}
      <StatusBar
        status={status}
        error={error}
        sandboxResult={sandboxResult}
        graphData={graphData}
        onRunSandbox={handleRunSandbox}
        sandboxLoading={sandboxLoading}
        animating={animating}
      />
    </div>
  );
}
