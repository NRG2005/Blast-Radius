"""
main.py — FastAPI backend for Blast Radius
"""
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from analyzer import analyze_change, DependencyGraph
from sandbox import run_sandbox, SandboxResult

app = FastAPI(title="Blast Radius API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent  # workspace root
SEED_REPOS_DIR = BASE_DIR / "seed-repos"

SCENARIOS = {
    "payment-service": SEED_REPOS_DIR / "payment-service",
    "user-api": SEED_REPOS_DIR / "user-api",
    "cache-lib": SEED_REPOS_DIR / "cache-lib",
}


# ── Request / Response models ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    scenario_id: Optional[str] = None       # use a preset seed repo
    repo_path: Optional[str] = None         # or provide a custom path
    change_description: str
    diff: Optional[str] = None


class SandboxRequest(BaseModel):
    scenario_id: Optional[str] = None
    repo_path: Optional[str] = None
    diff: str
    node_map: dict[str, str]                # node_id → file_path
    test_command: Optional[str] = None


class ExampleScenario(BaseModel):
    id: str
    name: str
    description: str
    change_description: str
    diff: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    return {"status": "ok", "openai_configured": has_key}


@app.get("/examples", response_model=list[ExampleScenario])
async def get_examples():
    """Return the list of pre-seeded demo scenarios."""
    examples = []
    for scenario_id, repo_dir in SCENARIOS.items():
        scenario_file = repo_dir / "scenario.json"
        if scenario_file.exists():
            data = json.loads(scenario_file.read_text())
            examples.append(ExampleScenario(
                id=data["id"],
                name=data["name"],
                description=data["description"],
                change_description=data["change_description"],
                diff=data["diff"],
            ))
    return examples


@app.post("/analyze", response_model=DependencyGraph)
async def analyze(req: AnalyzeRequest):
    """
    LLM-powered semantic dependency analysis.
    Returns a graph JSON with nodes and edges, risk-scored by the LLM.
    """
    repo_path = _resolve_repo_path(req.scenario_id, req.repo_path)

    diff = req.diff
    if req.scenario_id and not diff:
        # Load the scenario's canonical diff
        scenario_file = SCENARIOS[req.scenario_id] / "scenario.json"
        if scenario_file.exists():
            data = json.loads(scenario_file.read_text())
            diff = data.get("diff")

    try:
        graph = await analyze_change(
            repo_path=str(repo_path),
            change_description=req.change_description,
            diff=diff,
            timeout=60.0,
        )
        return graph
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=f"LLM timeout: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@app.post("/run-sandbox", response_model=SandboxResult)
async def run_sandbox_endpoint(req: SandboxRequest):
    """
    Apply the diff on a sandbox branch and run the test suite.
    Returns per-test pass/fail results mapped to graph node IDs.
    """
    repo_path = _resolve_repo_path(req.scenario_id, req.repo_path)

    diff = req.diff
    test_command = req.test_command

    # Load scenario defaults if needed
    if req.scenario_id:
        scenario_file = SCENARIOS[req.scenario_id] / "scenario.json"
        if scenario_file.exists():
            data = json.loads(scenario_file.read_text())
            if not diff:
                diff = data.get("diff", "")
            if not test_command:
                test_command = data.get("test_command")

    if not diff:
        raise HTTPException(status_code=400, detail="diff is required")

    try:
        result = await run_sandbox(
            repo_path=str(repo_path),
            diff=diff,
            scenario_id=req.scenario_id or "custom",
            node_map=req.node_map,
            test_command=test_command,
            timeout=90.0,
        )
        return result
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Test suite timeout: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sandbox run failed: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_repo_path(scenario_id: Optional[str], repo_path: Optional[str]) -> Path:
    if scenario_id:
        if scenario_id not in SCENARIOS:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown scenario '{scenario_id}'. Available: {list(SCENARIOS.keys())}",
            )
        return SCENARIOS[scenario_id]
    if repo_path:
        p = Path(repo_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Repo path not found: {repo_path}")
        return p
    raise HTTPException(status_code=400, detail="Either scenario_id or repo_path is required")
