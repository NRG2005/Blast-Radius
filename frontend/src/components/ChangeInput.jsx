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

  // The description/diff exactly as auto-filled from the selected scenario.
  // Used to detect "user edited the description but left the old diff in
  // place" — a real diff is concrete and dominates the LLM's reasoning, so
  // a stale one silently overrides whatever new description was typed,
  // making the result look unchanged/"hardcoded" even though the call is
  // genuinely fresh every time.
  const [baseline, setBaseline] = useState({ description: "", diff: "" });

  useEffect(() => {
    fetchExamples()
      .then((data) => {
        setExamples(data);
        if (data.length > 0) {
          setScenarioId(data[0].id);
          setChangeDescription(data[0].change_description);
          setDiff(data[0].diff);
          setBaseline({ description: data[0].change_description, diff: data[0].diff });
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
      setBaseline({ description: ex.change_description, diff: ex.diff });
      setShowDiff(!!ex.diff);
    } else {
      setChangeDescription("");
      setDiff("");
      setBaseline({ description: "", diff: "" });
      setShowDiff(false);
    }
  }

  function handleDescriptionChange(value) {
    setChangeDescription(value);
    // Only auto-clear if the diff still exactly matches what the scenario
    // loaded (i.e. the user hasn't intentionally hand-edited it) — don't
    // clobber a diff someone deliberately pasted alongside a refined
    // description.
    if (diff === baseline.diff && value !== baseline.description) {
      setDiff("");
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!changeDescription.trim()) return;
    onAnalyze({ scenarioId, changeDescription, diff });
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

      {/* Change description */}
      <div className="input-row">
        <label className="input-label" htmlFor="change-desc">
          Change Description
        </label>
        <textarea
          id="change-desc"
          className="input-textarea"
          value={changeDescription}
          onChange={(e) => handleDescriptionChange(e.target.value)}
          placeholder="Describe the proposed change in plain English…"
          rows={2}
          disabled={disabled || loading}
        />
        <p className="input-hint">
          Analyzed against the actual code in <strong>{examples.find((e) => e.id === scenarioId)?.name || "the selected repo"}</strong> — describe a real, plausible change to it, or edit the diff below directly.
        </p>
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
        disabled={disabled || loading || !changeDescription.trim()}
      >
        {loading ? (
          <>
            <span className="spinner" />
            Analyzing…
          </>
        ) : (
          <>
            Analyze Blast Radius
            <span className="cta-arrow">→</span>
          </>
        )}
      </button>
    </form>
  );
}
