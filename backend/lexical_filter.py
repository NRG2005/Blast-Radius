"""
lexical_filter.py

Deterministic, free, instant pre-filter — Layer 1 of the repo-scaling pipeline.
No LLM call. Finds files that are plausibly relevant to a change because they
textually reference the changed symbol names or the changed file's own module
name (which naturally catches most import statements too, across languages,
without needing a real per-language import parser).

This is intentionally cheap and over-inclusive: false positives just mean a
little more content reaches the deep-analyze layer; false negatives mean a
real dependent gets missed entirely, which is the worse failure mode.
"""
import re
from pathlib import Path
from typing import Optional

from repo_reader import SourceFile

# Tokens too common/short to be useful as search anchors
_STOPWORDS = {
    "self", "this", "true", "false", "none", "null", "return", "import",
    "from", "const", "let", "var", "def", "class", "function", "export",
    "default", "async", "await", "public", "private", "static", "void",
}

# Lines in a diff that carry the "old" or "new" value of the change
_DIFF_LINE_RE = re.compile(r"^[+-](?!\+\+|--)(.*)$", re.MULTILINE)

# Identifier-ish tokens: constants, assignment targets, def/class/function names
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]{2,})\s*[:=][^=]")
_DEF_RE = re.compile(
    r"\b(?:def|class|function)\s+([A-Za-z_][A-Za-z0-9_]{2,})"
    r"|\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]{2,})\s*="
)


def extract_changed_symbols(diff: Optional[str]) -> list[str]:
    """
    Pull identifier-like tokens out of a unified diff's changed lines.
    Prioritizes ALL_CAPS constants and assignment/def/class targets, since
    those are what a semantic dependent is most likely to reference by name.
    """
    if not diff:
        return []

    symbols: set[str] = set()
    for match in _DIFF_LINE_RE.finditer(diff):
        line = match.group(1)

        for m in _ASSIGNMENT_RE.finditer(line):
            symbols.add(m.group(1))
        for m in _DEF_RE.finditer(line):
            name = m.group(1) or m.group(2)
            if name:
                symbols.add(name)

        # ALL_CAPS constants anywhere on the line (e.g. DEFAULT_TIMEOUT)
        for tok in _IDENTIFIER_RE.findall(line):
            if tok.isupper() and "_" in tok or (tok.isupper() and len(tok) > 3):
                symbols.add(tok)

    return sorted(s for s in symbols if s.lower() not in _STOPWORDS)


def changed_file_from_diff(diff: Optional[str]) -> Optional[str]:
    """Extract the 'a/...' path from a unified diff's --- line."""
    if not diff:
        return None
    m = re.search(r"^--- a/(.+)$", diff, re.MULTILINE)
    return m.group(1).strip() if m else None


def find_lexical_candidates(
    files: list[SourceFile],
    symbols: list[str],
    changed_file_rel: Optional[str],
) -> dict[str, list[str]]:
    """
    Grep every file (except the changed file itself) for whole-word matches
    of `symbols`, plus the changed file's own module/basename — the latter
    catches most import statements across languages without a real parser.

    Returns {file_path: [matched_symbol, ...]}.
    """
    search_terms = set(symbols)
    if changed_file_rel:
        stem = Path(changed_file_rel).stem
        if stem and stem.lower() not in _STOPWORDS and len(stem) > 2:
            search_terms.add(stem)

    if not search_terms:
        return {}

    patterns = {
        term: re.compile(r"\b" + re.escape(term) + r"\b")
        for term in search_terms
    }

    matches: dict[str, list[str]] = {}
    for f in files:
        if changed_file_rel and f.path == changed_file_rel:
            continue
        hit_terms = [term for term, pat in patterns.items() if pat.search(f.content)]
        if hit_terms:
            matches[f.path] = hit_terms

    return matches
