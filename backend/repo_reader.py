"""
repo_reader.py

Walks a target repo and returns source files as context for the LLM.
"""
import os
from pathlib import Path
from typing import NamedTuple

# Source/config extensions across common backend + web-frontend stacks
INCLUDE_EXTENSIONS = {
    ".py", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".txt", ".md",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue",
    ".css", ".scss", ".html", ".ejs",
    ".go", ".rb", ".java", ".rs",
}
EXCLUDE_DIRS = {
    "__pycache__", ".git", ".git-seed-backup", ".pytest_cache", ".venv", "venv",
    "node_modules", ".mypy_cache", "dist", "build", "coverage", ".next", ".nuxt",
}
MAX_FILE_SIZE = 50_000  # bytes — skip very large generated files
MAX_FILES = 40          # cap total files to keep LLM context manageable


class SourceFile(NamedTuple):
    path: str       # relative path from repo root
    content: str


def read_repo(repo_path: str) -> list[SourceFile]:
    """
    Walk `repo_path` and return a list of SourceFile tuples.
    Files are sorted by path for reproducibility.
    """
    root = Path(repo_path).resolve()
    files: list[SourceFile] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for filename in sorted(filenames):
            filepath = Path(dirpath) / filename
            if filepath.suffix not in INCLUDE_EXTENSIONS:
                continue
            if filepath.stat().st_size > MAX_FILE_SIZE:
                continue

            rel_path = str(filepath.relative_to(root))
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            files.append(SourceFile(path=rel_path, content=content))

            if len(files) >= MAX_FILES:
                return files

    return sorted(files, key=lambda f: f.path)


def format_files_for_llm(files: list[SourceFile]) -> str:
    """Format source files into a single context string for the LLM prompt."""
    parts = []
    for f in files:
        parts.append(f"### FILE: {f.path}\n```\n{f.content}\n```")
    return "\n\n".join(parts)
