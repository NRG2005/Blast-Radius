import { useEffect, useState } from "react";
import { fetchExamples } from "../api";

export default function ChangeInput({
  onAnalyze,
  loading,
  disabled,
}) {
  const [examples, setExamples] = useState([]);
  const [scenarioId, setScenarioId] = useState("");
  const [changeDescription, setChangeDescription] = useState("");
  const [diff, setDiff] = useState("");
  const [showDiff, setShowDiff] = useState(false);
  const [repoPath, setRepoPath] = useState("");
  const [testCommand, setTestCommand] = useState("");

  useEffect(() => {
    fetchExamples()
      .then((data) => {
        setExamples(data);
        if (data.length > 0) {
          setScenarioId(data[0].id);
          setChangeDescription(data[0].change_description);
          setDiff(data[0].diff);
        }
      })
      .catch(console.error);
  }, []);

  function handleScenarioChange(id) {
    setScenarioId(id);
    const ex = examples.find((e) => e.id === id);
    if (ex) {
      setChangeDescription(ex.change_description);
      setDiff(ex.diff);
    }
  }

  const isCustom = scenarioId === "";

  function handleSubmit(e) {
    e.preventDefault();
    if (!changeDescription.trim()) return;
    if (isCustom && !repoPath.trim()) return;
    onAnalyze({
      scenarioId,
      changeDescription,
      diff,
      repoPath: isCustom ? repoPath.trim() : undefined,
      testCommand: isCustom ? testCommand.trim() || undefined : undefined,
    });
  }

  return (
    <form className="change-input" onSubmit={handleSubmit}>
      {/* Scenario selector */}
      <div className="input-row">
        <label className="input-label" htmlFor="scenario-select">
          Demo Scenario
        </label>
        <select
          id="scenario-select"
          className="input-select"
          value={scenarioId}
          onChange={(e) => handleScenarioChange(e.target.value)}
          disabled={disabled || loading}
        >
          <option value="">— Custom Repo —</option>
          {examples.map((ex) => (
            <option key={ex.id} value={ex.id}>
              {ex.name}
            </option>
          ))}
        </select>
      </div>

      {/* Custom repo path — only shown for "Custom Repo" */}
      {isCustom && (
        <>
          <div className="input-row">
            <label className="input-label" htmlFor="repo-path">
              Repo Path
            </label>
            <input
              id="repo-path"
              type="text"
              className="input-select"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              placeholder="/absolute/path/to/your/repo"
              disabled={disabled || loading}
            />
          </div>
          <div className="input-row">
            <label className="input-label" htmlFor="test-command">
              Test Command <span className="input-label-optional">(optional)</span>
            </label>
            <input
              id="test-command"
              type="text"
              className="input-select mono"
              value={testCommand}
              onChange={(e) => setTestCommand(e.target.value)}
              placeholder="e.g. npm test — used by Run It"
              disabled={disabled || loading}
            />
          </div>
        </>
      )}

      {/* Change description */}
      <div className="input-row">
        <label className="input-label" htmlFor="change-desc">
          Change Description
        </label>
        <textarea
          id="change-desc"
          className="input-textarea"
          value={changeDescription}
          onChange={(e) => setChangeDescription(e.target.value)}
          placeholder="Describe the proposed change in plain English…"
          rows={2}
          disabled={disabled || loading}
        />
      </div>

      {/* Diff (collapsible) */}
      <div className="input-row">
        <button
          type="button"
          className="toggle-diff-btn"
          onClick={() => setShowDiff((v) => !v)}
        >
          {showDiff ? "▲ Hide Diff" : "▼ Show Diff"} (optional)
        </button>
        {showDiff && (
          <textarea
            className="input-textarea mono"
            value={diff}
            onChange={(e) => setDiff(e.target.value)}
            placeholder="Paste a unified diff here (optional — helps the LLM)…"
            rows={6}
            disabled={disabled || loading}
          />
        )}
      </div>

      {/* Submit */}
      <button
        id="analyze-btn"
        type="submit"
        className={`analyze-btn ${loading ? "loading" : ""}`}
        disabled={disabled || loading || !changeDescription.trim() || (isCustom && !repoPath.trim())}
      >
        {loading ? (
          <>
            <span className="spinner" />
            Analyzing…
          </>
        ) : (
          <>
            <span className="btn-icon">⚡</span>
            Analyze Blast Radius
          </>
        )}
      </button>
    </form>
  );
}
