import Logo from "./Logo";
import "../landing.css";

export default function Landing({ onLaunch }) {
  return (
    <div className="landing">
      <div className="landing-field" aria-hidden="true">
        <span className="field-blob blob-red" />
        <span className="field-blob blob-amber" />
        <span className="field-blob blob-blue" />
        <span className="field-blob blob-green" />
        <span className="field-ring ring-1" />
        <span className="field-ring ring-2" />
        <span className="field-ring ring-3" />
      </div>

      <nav className="landing-nav">
        <div className="landing-brand">
          <Logo size={22} />
          <span>Blast Radius</span>
        </div>
        <button className="landing-nav-cta" onClick={onLaunch}>
          Launch Demo
        </button>
      </nav>

      <header className="landing-hero">
        <p className="landing-eyebrow">Pre-commit impact analysis</p>
        <h1 className="landing-headline">
          See what breaks
          <br />
          <span className="landing-headline-accent">before you commit.</span>
        </h1>
        <p className="landing-sub">
          Blast Radius reads a proposed change the way a senior engineer would —
          not just who calls this code, but whose tests, configs, and quiet
          assumptions it breaks. Then it proves the prediction by actually
          running the change, live, in a sandbox.
        </p>
        <div className="landing-cta-row">
          <button className="landing-cta-primary" onClick={onLaunch}>
            Launch Demo
            <span className="cta-arrow">→</span>
          </button>
          <a href="#how-it-works" className="landing-cta-secondary">
            See how it works
          </a>
        </div>
      </header>

      <section id="how-it-works" className="landing-steps">
        <div className="step-card">
          <span className="step-index" style={{ color: "var(--accent-will-break)" }}>01</span>
          <h3>Describe the change</h3>
          <p>A diff, or a plain-English description — a timeout dropping from 5s to 2s, a field getting renamed.</p>
        </div>
        <div className="step-card">
          <span className="step-index" style={{ color: "var(--accent-might-break)" }}>02</span>
          <h3>The blast radius gets mapped</h3>
          <p>An LLM reads the surrounding code and reasons about implicit contracts — retry math, hardcoded assumptions, config that quietly expects the old behavior.</p>
        </div>
        <div className="step-card">
          <span className="step-index" style={{ color: "var(--accent-review)" }}>03</span>
          <h3>Reality confirms the prediction</h3>
          <p>The change is applied on a sandboxed branch and the real test suite runs — every prediction gets to be proven right or wrong, live.</p>
        </div>
      </section>

      <footer className="landing-footer">
        <button className="landing-cta-primary landing-cta-final" onClick={onLaunch}>
          Launch Demo
          <span className="cta-arrow">→</span>
        </button>
        <p className="landing-footnote">Built for the OpenAI × Codex build event.</p>
      </footer>
    </div>
  );
}
