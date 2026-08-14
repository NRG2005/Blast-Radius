import Logo from "./Logo";

export default function StatusBar({
  status,
  error,
  sandboxResult,
  graphData,
  onRunSandbox,
  sandboxLoading,
  animating,
}) {
  if (error) {
    return (
      <div className="status-bar status-error">
        <span className="status-icon">⚠</span>
        <span className="status-msg">{error}</span>
      </div>
    );
  }

  if (animating) {
    return (
      <div className="status-bar status-running">
        <Logo size={17} />
        <span className="status-msg">Running sandbox tests…</span>
      </div>
    );
  }

  if (sandboxResult) {
    const { total_passed, total_failed, results } = sandboxResult;
    const hasBreaks = total_failed > 0;
    return (
      <div className={`status-bar ${hasBreaks ? "status-fail" : "status-pass"}`}>
        <span className="status-icon">{hasBreaks ? "✗" : "✓"}</span>
        <span className="status-msg">
          Sandbox complete: {total_passed} passed, {total_failed} failed
          {hasBreaks ? " — predictions confirmed!" : " — all green!"}
        </span>
        <div className="result-pills">
          {results.slice(0, 6).map((r) => (
            <span
              key={r.test_id}
              className={`result-pill pill-${r.status}`}
              title={r.test_id}
            >
              {r.status === "pass" ? "✓" : "✗"} {r.test_id.split("::").pop()}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (graphData?.nodes?.length > 0 && !sandboxLoading) {
    const willBreak = graphData.nodes.filter((n) => n.risk === "will_break").length;
    const mightBreak = graphData.nodes.filter((n) => n.risk === "might_break").length;
    return (
      <div className="status-bar status-ready">
        <div className="status-summary">
          <Logo size={17} />
          <span className="status-msg">
            Blast radius mapped — {willBreak} likely breaks, {mightBreak} potential issues
          </span>
          <div className="status-legend">
            <span className="legend-dot will-break" /> Will break
            <span className="legend-dot might-break" /> Might break
            <span className="legend-dot review" /> Review
          </div>
        </div>
        <button
          id="run-sandbox-btn"
          className={`run-btn ${sandboxLoading ? "loading" : ""}`}
          onClick={onRunSandbox}
          disabled={sandboxLoading}
        >
          {sandboxLoading ? (
            <><span className="spinner" /> Running…</>
          ) : (
            <><span className="btn-icon">▶</span> Run It</>
          )}
        </button>
      </div>
    );
  }

  if (status === "idle") {
    return (
      <div className="status-bar status-idle">
        <span className="status-icon">○</span>
        <span className="status-msg">Ready — select a scenario and analyze</span>
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div className="status-bar status-loading">
        <Logo size={17} />
        <span className="status-msg">Calling LLM for semantic analysis…</span>
        <span className="status-hint">This takes 10–30 seconds</span>
      </div>
    );
  }

  return null;
}
