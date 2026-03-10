"""
Load project context: generate a file tree and README summary to give the AI
an overview of the codebase before planning.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Directories and files to always skip
_SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", "node_modules",
    ".svelte-kit", "build", "dist", ".pytest_cache", ".mypy_cache",
}
_SKIP_EXTENSIONS = {".pyc", ".pyo", ".so", ".egg", ".db", ".sqlite", ".lock"}
_MAX_TREE_DEPTH = 4
_MAX_FILES_IN_TREE = 200


def build_file_tree(root: str, max_depth: int = _MAX_TREE_DEPTH) -> str:
    """Return a text file tree for the given root directory."""
    lines = [root]
    file_count = 0

    def _walk(path: Path, prefix: str, depth: int) -> None:
        nonlocal file_count
        if depth > max_depth or file_count >= _MAX_FILES_IN_TREE:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
        except PermissionError:
            return
        dirs = [e for e in entries if e.is_dir() and e.name not in _SKIP_DIRS]
        files = [e for e in entries if e.is_file() and e.suffix not in _SKIP_EXTENSIONS]

        for i, entry in enumerate(dirs + files):
            connector = "└── " if i == len(dirs + files) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            file_count += 1
            if entry.is_dir():
                extension = "    " if connector == "└── " else "│   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(Path(root), "", 0)

    if file_count >= _MAX_FILES_IN_TREE:
        lines.append(f"... (truncated at {_MAX_FILES_IN_TREE} entries)")

    return "\n".join(lines)


def load_readme(root: str) -> str:
    """Return the contents of README.md if it exists, otherwise empty string."""
    for name in ("README.md", "README.rst", "README.txt", "README"):
        path = Path(root) / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")[:4000]  # cap at 4k chars
            except Exception:
                pass
    return ""


def build_context_summary(root: str) -> str:
    """
    Build a short context block for the planner prompt.
    Includes the file tree and (if present) the README.
    """
    tree = build_file_tree(root)
    readme = load_readme(root)

    parts = [f"## Project File Tree\n```\n{tree}\n```"]
    if readme:
        parts.append(f"## README\n{readme}")
    return "\n\n".join(parts)
