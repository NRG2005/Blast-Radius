"""
triage.py

Layer 2 of the repo-scaling pipeline: a cheap, small-context LLM call that
looks at lightweight "cards" (path + first ~15 lines) for every file NOT
already caught by the free lexical pre-filter (lexical_filter.py), and picks
out files that might still be behaviorally coupled to the change despite
having no textual/lexical connection to it — e.g. a magic number, a
duplicated assumption, a parallel implementation.

Deliberately narrow scope: this stage does NOT try to explain *why* something
might be risky (that's Layer 3's job, with full file content). It only picks
candidates worth giving full content to.
"""
import json
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel

from repo_reader import SourceFile

TRIAGE_MODEL = "gpt-4o-mini"  # cheap/fast — this is a classification task, not deep reasoning
CARD_LINES = 15
MAX_CANDIDATES = 15

TRIAGE_SYSTEM_PROMPT = """You are helping scope a semantic impact analysis of a code change.

A cheap lexical search has already found every file that textually references the changed \
symbols or the changed file's own module name — you do NOT need to re-find those, they're \
listed below as "already included."

Your only job: scan the file tree and the short snippets below, and flag files that might \
still be behaviorally coupled to the change WITHOUT any textual/lexical connection to it — \
for example a hardcoded number that mirrors the old value, a test with a parallel/duplicated \
assumption, a config file describing timing or limits, or a doc file describing behavior that \
would become stale. Be selective — only flag files with a real plausible connection to the \
change, not files that are merely nearby or superficially similar.

Output ONLY a JSON object: {"candidates": [{"path": "...", "reason": "one short phrase"}]}
No markdown, no prose. Return at most 15 candidates. If nothing plausible, return an empty list.
"""


class TriageCandidate(BaseModel):
    path: str
    reason: str


def build_file_cards(files: list[SourceFile], max_lines: int = CARD_LINES) -> str:
    parts = []
    for f in files:
        lines = f.content.splitlines()[:max_lines]
        snippet = "\n".join(lines)
        parts.append(f"### {f.path}\n{snippet}")
    return "\n\n".join(parts)


async def triage_candidates(
    api_key: str,
    change_description: str,
    diff: Optional[str],
    already_included: list[str],
    card_files: list[SourceFile],
    timeout: float = 20.0,
) -> list[TriageCandidate]:
    """
    Ask a cheap model to shortlist additional files worth full analysis.
    Returns [] on any failure — triage is a nice-to-have; a failure here
    should degrade to "just the lexical matches," not break the whole run.
    """
    if not card_files:
        return []

    change_section = f"## Proposed Change\n{change_description}"
    if diff:
        change_section += f"\n\n## Diff\n```diff\n{diff}\n```"

    included_list = "\n".join(f"- {p}" for p in already_included) or "(none)"
    cards = build_file_cards(card_files)

    user_message = f"""{change_section}

## Already included via lexical search (do not re-flag these)
{included_list}

## Candidate files (path + first {CARD_LINES} lines)
{cards}

Return the JSON object described in the system prompt."""

    client = AsyncOpenAI(api_key=api_key)
    try:
        import asyncio
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=TRIAGE_MODEL,
                messages=[
                    {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000,
            ),
            timeout=timeout,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        candidates = [TriageCandidate(**c) for c in data.get("candidates", [])]
        valid_paths = {f.path for f in card_files}
        return [c for c in candidates if c.path in valid_paths][:MAX_CANDIDATES]
    except Exception:
        return []
