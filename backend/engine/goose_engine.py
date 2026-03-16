"""
Agentic coding engine inspired by Goose's architecture.

Instead of delegating to Aider, this engine uses direct LLM tool-calling:
  1. Send the task + developer tools to the LLM
  2. LLM responds with tool calls (read/write/edit files, run commands, etc.)
  3. Execute the tool calls and feed results back
  4. Repeat until the LLM responds with no tool calls (task complete)

This removes the Aider dependency entirely and gives full control over
the coding loop, rate limiting, and error handling.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import CodingEngine
from .result import EngineResult, TestResult

logger = logging.getLogger(__name__)

_MAX_TOOL_OUTPUT = 12000  # characters per tool result
_MAX_ITERATIONS = 100  # safety cap on tool-calling rounds per execute_task
_COMMAND_TIMEOUT = 120  # seconds

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format, used by litellm)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the repository root",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create a new file or completely overwrite an existing file. "
                "For small edits to existing files, prefer edit_file instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the repository root",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Edit a file by replacing an exact string match with new text. "
                "The old_text must match exactly (including whitespace/indentation). "
                "Only the first occurrence is replaced."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the repository root",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The exact text to find (must match exactly)",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The replacement text",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Execute a shell command in the repository directory. "
                "Use for running tests, installing deps, checking structure, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a tree-like format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to repo root (default: root)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to recurse (default: 3)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for a text pattern across files using grep. Returns matching lines with file paths and line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text or regex pattern to search for",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory or file to search in (default: repo root)",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob to filter files, e.g. '*.py' or '*.js'",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert software engineer implementing changes to a code repository.

You have tools for reading, writing, and editing files, running shell commands, \
listing directories, and searching file contents.

Guidelines:
- Start by exploring the repository structure (list_directory) to understand the codebase.
- Read relevant files before making changes.
- Use edit_file for targeted edits to existing files (preferred).
- Use write_file only for new files or complete rewrites.
- Run commands to verify your changes when appropriate.
- Make minimal, focused changes — only what the task requires.
- When you are done, respond with a brief summary of what you changed (no tool calls).\
"""


class GooseEngine(CodingEngine):
    """
    CodingEngine backed by a direct LLM tool-calling loop.

    Each instance operates on a single ephemeral repo clone (repo_path).
    Conversation history is maintained across inject_comment calls within
    the same task so the LLM retains context.
    """

    def __init__(
        self,
        repo_path: str,
        test_command: str = "pytest",
        lint_command: str = "ruff check .",
        llm_client=None,
        max_iterations: int = _MAX_ITERATIONS,
    ):
        self.repo_path = Path(repo_path)
        self.test_command = test_command
        self.lint_command = lint_command
        self.llm_client = llm_client
        self.max_iterations = max_iterations
        # Conversation state — persisted across inject_comment calls
        self._messages: list[dict] = []
        self._files_changed: set[str] = set()

    # ------------------------------------------------------------------
    # CodingEngine interface
    # ------------------------------------------------------------------

    def execute_task(self, task: str, files: list[str]) -> EngineResult:
        try:
            # Start fresh conversation for each task step
            self._messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ]
            self._files_changed.clear()

            summary = self._run_agent_loop()
            diff = self.get_diff()

            if not diff.strip():
                logger.warning(
                    "GooseEngine: task produced no file changes. Agent summary: %s",
                    summary[:200],
                )

            return EngineResult(
                success=True,
                diff=diff,
                files_changed=list(self._files_changed),
            )
        except Exception as exc:
            logger.error("GooseEngine.execute_task failed: %s", exc, exc_info=True)
            return EngineResult(
                success=False, diff="", files_changed=[], error=str(exc)
            )

    def get_diff(self) -> str:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def run_tests(self) -> TestResult:
        # Lint first
        lint = subprocess.run(
            self.lint_command.split(),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if lint.returncode != 0:
            return TestResult(
                passed=False,
                output=f"[LINT FAILED]\n{lint.stdout}\n{lint.stderr}",
            )
        # Test suite
        test = subprocess.run(
            self.test_command.split(),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return TestResult(
            passed=test.returncode == 0,
            output=test.stdout + test.stderr,
        )

    def inject_comment(self, comment: str) -> None:
        """Add a user comment to the ongoing conversation and continue the loop."""
        if not self._messages:
            raise RuntimeError("No active task — call execute_task first")
        self._messages.append({"role": "user", "content": comment})
        self._run_agent_loop()

    def reset(self) -> None:
        """Wipe the ephemeral repo clone."""
        if self.repo_path.exists():
            shutil.rmtree(self.repo_path)
            logger.info("Wiped ephemeral repo at %s", self.repo_path)
        self._messages.clear()
        self._files_changed.clear()

    # ------------------------------------------------------------------
    # Agentic loop
    # ------------------------------------------------------------------

    def _run_agent_loop(self) -> str:
        """
        Send messages to the LLM, execute any tool calls, feed results back.
        Repeats until the LLM responds with no tool calls or max iterations hit.
        Returns the final text response from the LLM.
        """
        for iteration in range(self.max_iterations):
            response_msg = self.llm_client.chat(self._messages, tools=TOOLS)

            # Append assistant message to conversation history
            self._messages.append(self._msg_to_dict(response_msg))

            tool_calls = getattr(response_msg, "tool_calls", None)
            if not tool_calls:
                # No tool calls — agent is done
                logger.info(
                    "Agent loop finished after %d iteration(s).", iteration + 1
                )
                return getattr(response_msg, "content", "") or ""

            # Execute each tool call
            logger.info(
                "Iteration %d: %d tool call(s) — %s",
                iteration + 1,
                len(tool_calls),
                ", ".join(tc.function.name for tc in tool_calls),
            )
            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                result = self._execute_tool(name, args)
                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": self._truncate(result),
                    }
                )

        logger.warning("Agent loop hit max iterations (%d).", self.max_iterations)
        return "(max iterations reached)"

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, name: str, args: dict) -> str:
        """Dispatch a tool call and return the result string."""
        try:
            if name == "read_file":
                return self._tool_read_file(args["path"])
            elif name == "write_file":
                return self._tool_write_file(args["path"], args["content"])
            elif name == "edit_file":
                return self._tool_edit_file(
                    args["path"], args["old_text"], args["new_text"]
                )
            elif name == "run_command":
                return self._tool_run_command(args["command"])
            elif name == "list_directory":
                return self._tool_list_directory(
                    args.get("path", "."), args.get("max_depth", 3)
                )
            elif name == "search_files":
                return self._tool_search_files(
                    args["pattern"],
                    args.get("path", "."),
                    args.get("file_pattern"),
                )
            else:
                return f"Error: Unknown tool '{name}'"
        except Exception as exc:
            logger.warning("Tool '%s' raised: %s", name, exc)
            return f"Error: {exc}"

    def _resolve_path(self, path: str) -> Path:
        """Resolve a relative path, preventing traversal outside the repo."""
        full = (self.repo_path / path).resolve()
        repo_resolved = self.repo_path.resolve()
        if not str(full).startswith(str(repo_resolved)):
            raise ValueError(f"Path traversal blocked: {path}")
        return full

    def _tool_read_file(self, path: str) -> str:
        full = self._resolve_path(path)
        if not full.exists():
            return f"Error: File not found: {path}"
        if not full.is_file():
            return f"Error: Not a file: {path}"
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"Error reading {path}: {exc}"
        return content

    def _tool_write_file(self, path: str, content: str) -> str:
        full = self._resolve_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        self._files_changed.add(path)
        logger.info("write_file: %s (%d chars)", path, len(content))
        return f"File written: {path} ({len(content)} characters)"

    def _tool_edit_file(self, path: str, old_text: str, new_text: str) -> str:
        full = self._resolve_path(path)
        if not full.exists():
            return f"Error: File not found: {path}"
        content = full.read_text(encoding="utf-8", errors="replace")
        if old_text not in content:
            return (
                f"Error: Could not find the specified text in {path}. "
                "Make sure old_text matches exactly (including whitespace and indentation)."
            )
        new_content = content.replace(old_text, new_text, 1)
        full.write_text(new_content, encoding="utf-8")
        self._files_changed.add(path)
        logger.info("edit_file: %s", path)
        return f"File edited: {path}"

    def _tool_run_command(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=_COMMAND_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {_COMMAND_TIMEOUT}s"
        output = result.stdout + result.stderr
        if result.returncode != 0:
            output = f"[exit code {result.returncode}]\n{output}"
        return output or "(no output)"

    def _tool_list_directory(self, path: str = ".", max_depth: int = 3) -> str:
        full = self._resolve_path(path)
        if not full.is_dir():
            return f"Error: Not a directory: {path}"

        skip = {
            ".git", "__pycache__", "node_modules", "venv", ".venv",
            ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
            ".next", ".nuxt", ".egg-info",
        }
        lines: list[str] = []

        def _walk(dir_path: Path, depth: int) -> None:
            if depth > max_depth or len(lines) >= 500:
                return
            try:
                entries = sorted(
                    dir_path.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except PermissionError:
                return
            for entry in entries:
                if entry.name.startswith(".") and entry.is_dir():
                    continue
                if entry.name in skip:
                    continue
                rel = entry.relative_to(self.repo_path)
                if entry.is_dir():
                    lines.append(f"{rel}/")
                    _walk(entry, depth + 1)
                else:
                    lines.append(str(rel))
                if len(lines) >= 500:
                    return

        _walk(full, 0)
        result = "\n".join(lines)
        if len(lines) >= 500:
            result += "\n... (truncated at 500 entries)"
        return result or "(empty directory)"

    def _tool_search_files(
        self, pattern: str, path: str = ".", file_pattern: str | None = None
    ) -> str:
        cmd = ["grep", "-rn", "--max-count=50"]
        if file_pattern:
            cmd += ["--include", file_pattern]
        cmd += [pattern, path]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return "Error: Search timed out"
        return result.stdout or "(no matches)"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _msg_to_dict(msg: Any) -> dict:
        """Convert a litellm message object to a plain dict for the messages list."""
        d: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if getattr(msg, "tool_calls", None):
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        return d

    @staticmethod
    def _truncate(text: str) -> str:
        """Truncate tool output to stay within context limits."""
        if len(text) <= _MAX_TOOL_OUTPUT:
            return text
        half = _MAX_TOOL_OUTPUT // 2
        return (
            text[:half]
            + f"\n\n... ({len(text) - _MAX_TOOL_OUTPUT} characters truncated) ...\n\n"
            + text[-half:]
        )
