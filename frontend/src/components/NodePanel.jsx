const RISK_LABELS = {
  change: { label: "PROPOSED CHANGE", color: "#9b8cf0", bg: "#9b8cf015" },
  will_break: { label: "WILL BREAK", color: "#ee5257", bg: "#ee525715" },
  might_break: { label: "MIGHT BREAK", color: "#f0a63e", bg: "#f0a63e15" },
  review: { label: "WORTH REVIEWING", color: "#4fa6f2", bg: "#4fa6f215" },
  safe: { label: "SAFE", color: "#34c17e", bg: "#34c17e15" },
};

const CONFIRMED_LABELS = {
  pass: { label: "✓ CONFIRMED PASSING", color: "#34c17e", bg: "#34c17e15" },
  fail: { label: "✗ CONFIRMED FAILING", color: "#ee5257", bg: "#ee525715" },
  error: { label: "⚠ ERROR", color: "#f2884a", bg: "#f2884a15" },
  not_run: { label: "— NOT RUN", color: "#56565f", bg: "#56565f15" },
};

const NODE_TYPE_ICONS = {
  change: "⚡",
  test: "🧪",
  module: "📦",
  config: "⚙️",
};

export default function NodePanel({ node, sandboxResult, onClose }) {
  if (!node) return null;

  const riskInfo = RISK_LABELS[node.risk] || RISK_LABELS.review;
  const confirmedInfo = sandboxResult ? CONFIRMED_LABELS[sandboxResult.status] : null;

  return (
    <div className="node-panel">
      <button className="node-panel-close" onClick={onClose} aria-label="Close panel">
        ✕
      </button>

      <div className="node-panel-header">
        <span className="node-type-icon">{NODE_TYPE_ICONS[node.node_type] || "📄"}</span>
        <div>
          <h2 className="node-panel-title">{node.label}</h2>
          <p className="node-panel-path">{node.file_path}</p>
        </div>
      </div>

      {/* Risk badge */}
      <div
        className="risk-badge"
        style={{ color: riskInfo.color, background: riskInfo.bg, borderColor: riskInfo.color + "44" }}
      >
        <span className="risk-dot" style={{ background: riskInfo.color }} />
        {riskInfo.label}
      </div>

      {/* Confirmed result badge */}
      {confirmedInfo && (
        <div
          className="risk-badge confirmed-badge"
          style={{ color: confirmedInfo.color, background: confirmedInfo.bg, borderColor: confirmedInfo.color + "44" }}
        >
          <span className="risk-dot" style={{ background: confirmedInfo.color }} />
          {confirmedInfo.label}
          {sandboxResult.test_id && (
            <span className="test-id">{sandboxResult.test_id}</span>
          )}
        </div>
      )}

      {/* LLM Justification */}
      <div className="node-panel-section">
        <h3 className="section-label">LLM Analysis</h3>
        <p className="justification-text" style={{ borderLeftColor: riskInfo.color }}>
          {node.justification}
        </p>
      </div>

      {/* Node metadata */}
      <div className="node-panel-section">
        <h3 className="section-label">Metadata</h3>
        <dl className="meta-list">
          <dt>Type</dt>
          <dd>{node.node_type}</dd>
          <dt>Risk level</dt>
          <dd style={{ color: riskInfo.color }}>{node.risk.replace("_", " ")}</dd>
          <dt>Node ID</dt>
          <dd className="mono">{node.id}</dd>
        </dl>
      </div>
    </div>
  );
}
