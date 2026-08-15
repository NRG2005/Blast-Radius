# Blast Radius

**Pre-commit semantic impact analysis.** See what breaks before you commit — not just who calls the changed code, but whose tests, configs, and quiet assumptions it violates. Then prove it, live, by actually running the change in a sandbox.

Built for the OpenAI × Codex build event.

## Demo Video

<video src="demo/demo-video.mp4" controls width="100%"></video>

(If the player above doesn't render, [download/view the video directly](demo/demo-video.mp4).)

## The Problem

The scariest bugs from a code change aren't the ones where you're looking — they're three files away, invisible to a simple grep or call-graph. A test that silently encodes an assumption about a timeout value. A retry loop calibrated for the old behavior. A config that expects a field name that just got renamed. Direct-reference tools (grep, "find usages," most AI coding assistants) only catch the callers. They don't catch the *semantic* dependents — the code that's coupled to the old behavior without ever referencing it by name.

## What It Does

1. **Analyze** — give Blast Radius a proposed change: a diff, or a plain-English description. An LLM reads the relevant source and reasons about semantic risk, not just direct references: tests whose assumptions the change violates, config or comments that assume the old behavior, retry/timing logic calibrated for the old value.
2. **Visualize** — every dependent is scored (`will_break`, `might_break`, `review`, `safe`) and rendered as an interactive force-directed graph, the proposed change at the center, risk radiating outward in color-coded rings. Click any node to see the LLM's actual justification.
3. **Confirm** — one click applies the change on a sandboxed git branch, runs the real test suite, and updates the graph with actual pass/fail results. Predictions get confirmed or corrected against reality, live — nothing here is scripted or mocked.

## Why This Matters at an OpenAI × Codex Event

As agentic coding tools make it faster and cheaper to generate changes, the bottleneck shifts from "can we write the change" to "can we trust it." Blast Radius isn't competing with Codex — it's the safety net underneath it. It doesn't care whether a diff came from a human or an agent; it just tells you, before you commit, what you don't know you broke.

## Architecture

**Backend** — Python / FastAPI
- `analyzer.py` — calls OpenAI (GPT-4o) with the repo's relevant source as context, prompting it to identify semantic dependents and assign risk scores with concrete justifications grounded in *why* the assumption breaks, not just "this file imports X."
- `repo_reader.py` — walks a target repo, filtering to relevant source/config files across common backend and web-frontend stacks (Python, JS/TS/JSX/TSX, CSS, HTML, Go, Ruby, Java, Rust).
- `sandbox.py` — creates a sandboxed git branch, applies the diff, runs the test suite, parses pass/fail results, and always restores the repo to a clean state afterward.
- **Repo-scaling triage pipeline** (`lexical_filter.py`, `triage.py`) — for repos too large to dump wholesale into an LLM context: a free lexical/import pre-filter finds directly-referenced files, then a cheap secondary LLM call triages the rest for non-obvious candidates (magic numbers, parallel assumptions) before the full analysis runs on the curated set.

**Frontend** — React + Vite
- Force-directed dependency graph (`react-force-graph-2d`), risk-color-coded, with live pass/fail confirmation animation.
- Custom landing page and demo UI, dark-themed, built around the same risk-color language throughout.
- Supports both curated demo scenarios and arbitrary local repositories via a custom repo path.

## Seed Demo Scenarios

Three small, self-contained repos, each with a real, verified, non-obvious break:

| Repo | Change | The non-obvious break |
|---|---|---|
| `payment-service` | Reduce `DEFAULT_TIMEOUT` 5s → 2s | A retry-loop test asserts `DEFAULT_TIMEOUT >= 3.0s` — a timing contract never imported or referenced by name anywhere near the change. |
| `user-api` | Rename `username` → `user_name` | Tests assert on the literal JSON key `"username"` in serialized output, never touching `user.username` directly — the rename ripples through string-based contract tests. |
| `cache-lib` | Reduce `DEFAULT_TTL` 300s → 60s | An integration test's sleep duration is calibrated against the old TTL, with no direct reference to the constant. |

Each was independently verified end-to-end: the diff applies cleanly, the predicted test fails for exactly the predicted reason, and the sandbox run confirms it live.

## Running Locally

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.
