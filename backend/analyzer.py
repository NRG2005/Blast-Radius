"""
analyzer.py

LLM-based semantic dependency analysis.
Calls OpenAI to identify which files/tests are at risk from a proposed change,
and returns a structured graph JSON.
"""
import json
import os
import asyncio
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel

from repo_reader import read_repo, read_repo_tree, format_files_for_llm, MAX_FILES, SourceFile
from lexical_filter import extract_changed_symbols, changed_file_from_diff, find_lexical_candidates
from triage import triage_candidates

# ── Pydantic models for structured output ────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str
    file_path: str
    risk: str          # "will_break" | "might_break" | "review" | "safe" | "change"
    justification: str
    node_type: str     # "change" | "test" | "module" | "config"


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str  # "directly_calls" | "implicitly_assumes" | "config_reference" | "comment_reference"


class DependencyGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: str


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior software engineer performing a pre-commit impact analysis.

Given a proposed code change and the full source files of a repository, your job is to:
1. Identify every file, test, function, or config that could be affected by this change
2. Classify each dependent by SEMANTIC RISK — not just direct callers, but:
   - Tests whose ASSUMPTIONS the change violates (even if they don't import the changed value)
   - Config or comments that assume the OLD behavior
   - Code that implicitly relies on the current behavior without directly referencing it
   - Retry logic, timing logic, or contracts calibrated for the old value
3. Assign a risk level to each:
   - "will_break": The change will definitely cause this to fail
   - "might_break": The change likely breaks an implicit assumption here
   - "review": Worth reviewing — may be fine but has indirect dependency
   - "safe": Explicitly unaffected, include for graph completeness only if relevant

CRITICAL: Your justifications must explain the SEMANTIC REASON for risk, not just "this file imports X".
Instead of "test_billing.py calls charge_user which calls fetch_user" — write WHY the assumption breaks:
"test_charge_with_real_timeout_budget encodes an implicit timing contract: DEFAULT_TIMEOUT >= 3.0s.
With timeout=2.0s, the assertion DEFAULT_TIMEOUT >= MINIMUM_ACCEPTABLE_TIMEOUT fails, because
the retry loop was calibrated for a 5s upstream budget and 2s is below the minimum."

Output ONLY a valid JSON object matching this exact schema. No markdown, no prose:
{
  "nodes": [
    {
      "id": "node_0",
      "label": "Short display name",
      "file_path": "relative/path/to/file.py",
      "risk": "change",
      "justification": "This is the proposed change itself",
      "node_type": "change"
    },
    {
      "id": "node_1",
      "label": "TestRetryTiming",
      "file_path": "payment_service/tests/test_billing.py",
      "risk": "will_break",
      "justification": "..detailed semantic reason...",
      "node_type": "test"
    }
  ],
  "edges": [
    {
      "source": "node_0",
      "target": "node_1",
      "relationship": "implicitly_assumes"
    }
  ],
  "summary": "One-paragraph summary of the blast radius for the developer."
}

node_type must be one of: "change", "test", "module", "config"
risk must be one of: "change", "will_break", "might_break", "review", "safe"
relationship must be one of: "directly_calls", "implicitly_assumes", "config_reference", "comment_reference", "inherits"

Include the changed file itself as node_0 with risk="change". Include 5-12 dependent nodes total.
Do not include files that have zero connection to the change.
"""


async def _run_deep_analysis(
    files: list[SourceFile],
    change_description: str,
    diff: Optional[str],
    timeout: float,
    api_key: str,
) -> DependencyGraph:
    """
    Shared LLM call: given a curated set of SourceFiles, run the actual
    semantic risk analysis and return the graph. Extracted so both the
    original (unscaled) and the new repo-scaling path call the exact same
    prompt/parsing logic — no forked copy of SYSTEM_PROMPT to drift.
    """
    repo_context = format_files_for_llm(files)

    change_section = f"## Proposed Change\n{change_description}"
    if diff:
        change_section += f"\n\n## Diff\n```diff\n{diff}\n```"

    user_message = f"""{change_section}

## Repository Source Files
{repo_context}

Analyze the blast radius of this change. Return only the JSON graph object."""

    client = AsyncOpenAI(api_key=api_key)

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=4000,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"LLM analysis timed out after {timeout}s")

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
        graph = DependencyGraph(**data)
    except Exception as exc:
        raise ValueError(f"LLM returned invalid graph structure: {exc}\nRaw: {raw[:500]}")

    return graph


async def analyze_change(
    repo_path: str,
    change_description: str,
    diff: Optional[str] = None,
    timeout: float = 45.0,
) -> DependencyGraph:
    """
    Call the LLM to produce a semantic dependency graph for the proposed change.
    Unscaled path — reads up to MAX_FILES files (today: first 40, alphabetically).
    Behavior is unchanged from before the repo-scaling work; this is what every
    seed-repo demo scenario still calls.

    Returns a DependencyGraph. Raises on hard failure (no partial results).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    files = read_repo(repo_path)
    return await _run_deep_analysis(files, change_description, diff, timeout, api_key)


async def analyze_change_scaled(
    repo_path: str,
    change_description: str,
    diff: Optional[str] = None,
    timeout: float = 60.0,
) -> DependencyGraph:
    """
    Repo-scaling path for repos larger than MAX_FILES. Three layers:
      1. Free lexical/import pre-filter (lexical_filter.py) — files that
         textually reference the changed symbols or module name.
      2. Cheap LLM triage (triage.py) over lightweight file cards — finds
         additional candidates with NO lexical connection (magic numbers,
         parallel assumptions) that Layer 1 can't catch.
      3. The exact same deep-analysis call as analyze_change, just fed the
         curated file set from layers 1+2 instead of the full repo.

    If the repo has no diff to anchor against, or fits under MAX_FILES anyway,
    this degrades to the same behavior as analyze_change.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    tree = read_repo_tree(repo_path)

    if len(tree) <= MAX_FILES or not diff:
        # Small enough (or no diff to anchor triage against) — no need to scale.
        files = tree if len(tree) <= MAX_FILES else tree[:MAX_FILES]
        return await _run_deep_analysis(files, change_description, diff, timeout, api_key)

    changed_file = changed_file_from_diff(diff)
    symbols = extract_changed_symbols(diff)

    lexical_matches = find_lexical_candidates(tree, symbols, changed_file)
    direct_files = [
        f for f in tree
        if f.path in lexical_matches or f.path == changed_file
    ]
    direct_paths = {f.path for f in direct_files}
    remaining = [f for f in tree if f.path not in direct_paths]

    triage_results = await triage_candidates(
        api_key=api_key,
        change_description=change_description,
        diff=diff,
        already_included=sorted(direct_paths),
        card_files=remaining,
        timeout=min(timeout, 25.0),
    )
    extra_paths = {c.path for c in triage_results}
    extra_files = [f for f in remaining if f.path in extra_paths]

    final_files = direct_files + extra_files
    if not final_files:
        # Pathological case: nothing lexically or semantically matched.
        # Fall back to the naive cap rather than sending an empty context.
        final_files = tree[:MAX_FILES]

    return await _run_deep_analysis(final_files, change_description, diff, timeout, api_key)
