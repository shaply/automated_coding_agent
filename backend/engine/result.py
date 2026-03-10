from dataclasses import dataclass, field


@dataclass
class EngineResult:
    success: bool
    diff: str
    files_changed: list[str]
    error: str | None = None


@dataclass
class TestResult:
    passed: bool
    output: str
    step: int | None = None
