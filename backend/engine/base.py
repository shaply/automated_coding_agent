from abc import ABC, abstractmethod
from .result import EngineResult, TestResult


class CodingEngine(ABC):
    """
    Abstract base class for coding engines.

    All orchestrator code should depend only on this interface, never on a
    concrete implementation. To swap engines, implement this class and update
    config.yaml — nothing else changes.
    """

    @abstractmethod
    def execute_task(self, task: str, files: list[str]) -> EngineResult:
        """Given a task description and relevant files, implement the changes."""

    @abstractmethod
    def get_diff(self) -> str:
        """Return a unified diff of all changes made so far."""

    @abstractmethod
    def run_tests(self) -> TestResult:
        """Run the project's test suite and return results."""

    @abstractmethod
    def inject_comment(self, comment: str) -> None:
        """Accept a mid-implementation comment from the user and adjust course."""

    @abstractmethod
    def reset(self) -> None:
        """Discard all changes (user rejected the final review)."""
