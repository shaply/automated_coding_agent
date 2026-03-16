import subprocess
import shutil
import logging
from pathlib import Path

from .base import CodingEngine
from .result import EngineResult, TestResult

logger = logging.getLogger(__name__)


class AiderEngine(CodingEngine):
    """
    CodingEngine implementation backed by Aider.

    Aider handles context window management, file editing, and diff generation.
    Each instance operates on a single ephemeral repo clone (repo_path).
    """

    def __init__(self, model_name: str, repo_path: str, test_command: str = "pytest", lint_command: str = "ruff check .", llm_client=None):
        self.model_name = model_name
        self.repo_path = Path(repo_path)
        self.test_command = test_command
        self.lint_command = lint_command
        self.llm_client = llm_client
        self._coder = None

    def _current_model(self) -> str:
        """Return the best available model, consulting llm_client budget if available."""
        if self.llm_client is not None:
            return self.llm_client.select_model()
        return self.model_name

    def _find_anchor_file(self) -> str:
        """
        Return the path of a single file inside the cloned repo.
        Aider uses this to locate the git root and build its repo map.
        Prefer well-known entry points so the map is most useful.
        """
        candidates = [
            "README.md", "README.txt", "package.json", "pyproject.toml",
            "setup.py", "Cargo.toml", "go.mod", "pom.xml",
        ]
        for name in candidates:
            p = self.repo_path / name
            if p.exists():
                return str(p)
        # Fall back to any regular file directly in the repo root
        for p in self.repo_path.iterdir():
            if p.is_file() and not p.name.startswith("."):
                return str(p)
        return ""

    def _get_coder(self, files: list[str]):
        """Lazily initialize the Aider coder for the current task."""
        from aider.coders import Coder
        from aider.models import Model
        from aider.io import InputOutput

        io = InputOutput(yes=True)  # auto-confirm, no interactive prompts
        model = Model(self._current_model())

        # If no specific files are requested, pass a single anchor file so Aider
        # can find the correct git root and build its repo map automatically.
        # Passing all files sends their full content to the LLM and blows past
        # token-per-minute limits on free-tier providers (e.g. Groq's 12k TPM).
        if files:
            fnames = [str(self.repo_path / f) for f in files]
        else:
            fnames = [self._find_anchor_file()]
            logger.info("AiderEngine: using anchor file %s — Aider repo map will cover the rest.", fnames[0] if fnames[0] else "(none found)")

        coder = Coder.create(
            main_model=model,
            fnames=fnames,
            auto_commits=False,  # orchestrator controls commits
            io=io,
        )
        return coder

    def execute_task(self, task: str, files: list[str]) -> EngineResult:
        try:
            self._coder = self._get_coder(files)
            self._coder.run(task)
            diff = self.get_diff()
            if not diff.strip():
                logger.warning("AiderEngine: step produced no file changes — Aider may not have found relevant files.")
            return EngineResult(success=True, diff=diff, files_changed=files)
        except Exception as exc:
            logger.error("AiderEngine.execute_task failed: %s", exc)
            return EngineResult(success=False, diff="", files_changed=files, error=str(exc))

    def get_diff(self) -> str:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def run_tests(self) -> TestResult:
        # Run linter first
        lint_result = subprocess.run(
            self.lint_command.split(),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if lint_result.returncode != 0:
            return TestResult(
                passed=False,
                output=f"[LINT FAILED]\n{lint_result.stdout}\n{lint_result.stderr}",
            )

        # Run test suite
        test_result = subprocess.run(
            self.test_command.split(),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        passed = test_result.returncode == 0
        return TestResult(
            passed=passed,
            output=test_result.stdout + test_result.stderr,
        )

    def inject_comment(self, comment: str) -> None:
        if self._coder is None:
            raise RuntimeError("No active task — call execute_task first")
        self._coder.run(comment)

    def reset(self) -> None:
        """Wipe the ephemeral repo clone entirely."""
        if self.repo_path.exists():
            shutil.rmtree(self.repo_path)
            logger.info("Wiped ephemeral repo at %s", self.repo_path)
        self._coder = None
