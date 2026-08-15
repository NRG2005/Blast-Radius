"""
sandbox.py

Creates a sandboxed git branch, applies a diff, runs the test suite,
and returns per-test pass/fail results.
"""
import asyncio
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class TestResult(BaseModel):
    node_id: str        # maps to graph node ID
    test_id: str        # pytest test ID
    status: str         # "pass" | "fail" | "error" | "not_run"
    output: str         # captured output snippet


class SandboxResult(BaseModel):
    branch_name: str
    results: list[TestResult]
    total_passed: int
    total_failed: int
    raw_output: str


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    """
    Strip ANSI color escape codes from subprocess output. Without this, a
    test runner that emits color (pytest can, depending on the ambient
    environment/PATH's python3 and its config, regardless of --color=no
    flags we pass) breaks the PASSED/FAILED regex below silently — every
    test then parses as unmatched, producing a false "0 passed, 0 failed,
    all green" instead of the real result.
    """
    return _ANSI_ESCAPE_RE.sub("", text)


def _run_git(args: list[str], cwd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _apply_diff(repo_path: str, diff: str) -> None:
    """Apply a unified diff to the working tree using git apply."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
        f.write(diff)
        patch_file = f.name
    try:
        result = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", patch_file],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try with --reject for partial applies
            raise RuntimeError(
                f"git apply failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
    finally:
        os.unlink(patch_file)


def _apply_diff_sed(repo_path: str, diff: str) -> None:
    """
    Fallback: parse the diff and apply changes directly using Python file I/O.
    Handles simple single-line substitutions robustly.
    """
    current_file = None
    old_lines: list[str] = []
    new_lines: list[str] = []

    for line in diff.splitlines():
        if line.startswith("--- a/"):
            current_file = line[6:]
            old_lines = []
            new_lines = []
        elif line.startswith("+++ b/"):
            pass  # new file path, we already have it from ---
        elif line.startswith("-") and not line.startswith("---"):
            old_lines.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            new_lines.append(line[1:])
        elif line.startswith("@@"):
            # Apply any accumulated changes to current_file
            if current_file and old_lines:
                _patch_file(repo_path, current_file, old_lines, new_lines)
            old_lines = []
            new_lines = []

    # Apply remaining
    if current_file and old_lines:
        _patch_file(repo_path, current_file, old_lines, new_lines)


def _patch_file(repo_path: str, rel_path: str, old_lines: list[str], new_lines: list[str]) -> None:
    filepath = Path(repo_path) / rel_path
    if not filepath.exists():
        return
    content = filepath.read_text(encoding="utf-8")
    old_text = "\n".join(old_lines)
    new_text = "\n".join(new_lines)
    if old_text in content:
        content = content.replace(old_text, new_text, 1)
        filepath.write_text(content, encoding="utf-8")


async def run_sandbox(
    repo_path: str,
    diff: str,
    scenario_id: str,
    node_map: dict[str, str],  # node_id → file_path (for matching test results)
    test_command: Optional[str] = None,
    timeout: float = 60.0,
) -> SandboxResult:
    """
    1. Create a new branch blast-radius/sandbox-{timestamp}
    2. Apply the diff
    3. Run the test suite
    4. Parse results and map back to graph nodes
    5. Restore original branch
    """
    branch_name = f"blast-radius/sandbox-{int(time.time())}"
    original_branch = "main"

    try:
        # Get current branch
        result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, check=False)
        if result.returncode == 0:
            original_branch = result.stdout.strip()
    except Exception:
        pass

    try:
        # Create and checkout sandbox branch
        _run_git(["checkout", "-b", branch_name], cwd=repo_path)

        # Apply the diff
        try:
            _apply_diff(repo_path, diff)
        except RuntimeError:
            # Fallback to Python-based patch
            _apply_diff_sed(repo_path, diff)

        # Commit the applied change onto the sandbox branch so it's isolated
        # there — otherwise it's an uncommitted working-tree change that git
        # carries across the checkout back to the original branch, leaving
        # the repo dirty (and breaking subsequent sandbox runs).
        # `-a` stages modifications to already-tracked files only — it must
        # NOT pick up unrelated untracked files (e.g. scenario.json,
        # __pycache__), since those would then get deleted by git when we
        # check back out to a branch that doesn't track them.
        _run_git(["commit", "-a", "-m", "blast-radius: apply proposed change", "--no-verify"], cwd=repo_path, check=False)

        # Run tests. Force color off at the source (belt-and-suspenders —
        # the output is also ANSI-stripped below regardless, since color
        # can leak in from the ambient environment/PATH's python3/pytest
        # regardless of these flags, e.g. a global pytest.ini or a
        # different interpreter than expected picking up color-by-default).
        cmd = shlex.split(test_command or "python3 -m pytest -v --tb=short -m 'not slow'")
        env = {**os.environ, "PY_COLORS": "0", "NO_COLOR": "1", "PYTEST_ADDOPTS": "--color=no"}
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        try:
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"Test suite timed out after {timeout}s")

        raw_output = _strip_ansi(stdout_bytes.decode("utf-8", errors="replace"))

        # Parse pytest output
        test_results = _parse_pytest_output(raw_output, node_map)

        passed = sum(1 for r in test_results if r.status == "pass")
        failed = sum(1 for r in test_results if r.status in ("fail", "error"))

        return SandboxResult(
            branch_name=branch_name,
            results=test_results,
            total_passed=passed,
            total_failed=failed,
            raw_output=raw_output,
        )

    finally:
        # Always restore original branch and delete sandbox branch.
        # Discard any uncommitted working-tree state first (in case the
        # diff apply or commit above didn't fully land) so the checkout
        # back to original_branch is guaranteed clean.
        try:
            _run_git(["checkout", "--", "."], cwd=repo_path, check=False)
            _run_git(["checkout", original_branch], cwd=repo_path, check=False)
            _run_git(["branch", "-D", branch_name], cwd=repo_path, check=False)
        except Exception:
            pass


def _parse_pytest_output(output: str, node_map: dict[str, str]) -> list[TestResult]:
    """
    Parse pytest -v output and produce TestResult list.
    Maps each test to a graph node_id by matching file paths.
    """
    results: list[TestResult] = []
    # Match lines like: "path/to/test_foo.py::TestClass::test_method PASSED"
    # NOTE: the separator must be [ \t]+, not \s+ — \s+ matches newlines too,
    # which lets the regex span from one summary line's bare "FAILED test_id"
    # (no trailing reason text) across the \n into the next line's "FAILED",
    # producing a bogus test_id like "FAILED path/to/test.py::...\nFAILED".
    pattern = re.compile(
        r"^(.+?::[\w\[\]]+)[ \t]+(PASSED|FAILED|ERROR|XFAIL|XPASS|SKIPPED)",
        re.MULTILINE,
    )

    found: dict[str, str] = {}  # test_id → status
    for match in pattern.finditer(output):
        test_id = match.group(1).strip()
        status_str = match.group(2).strip()
        found[test_id] = status_str

    # Map test IDs to node IDs
    reverse_map = {v: k for k, v in node_map.items()}  # file_path → node_id

    for test_id, status_str in found.items():
        # Find the file path prefix
        file_part = test_id.split("::")[0]
        node_id = None
        for file_path, nid in reverse_map.items():
            if file_path in file_part or file_part in file_path:
                node_id = nid
                break

        status = {
            "PASSED": "pass",
            "FAILED": "fail",
            "ERROR": "error",
            "XFAIL": "pass",
            "XPASS": "fail",
            "SKIPPED": "pass",
        }.get(status_str, "not_run")

        results.append(TestResult(
            node_id=node_id or "unknown",
            test_id=test_id,
            status=status,
            output="",
        ))

    return results
