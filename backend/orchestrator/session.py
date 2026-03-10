"""
Persistent session state — survives restarts via JSON on disk.

State machine transitions:
  idle → planning → awaiting_plan_review → coding → awaiting_diff_review
  → (approved) done | (rejected) idle
  → halted (on git error or credit exhaustion)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

AgentStatus = Literal[
    "idle",
    "planning",
    "awaiting_plan_review",
    "coding",
    "awaiting_diff_review",
    "halted",
    "halted:credits_exhausted",
    "done",
]


@dataclass
class SessionState:
    task_id: str
    status: AgentStatus = "idle"
    task_description: str = ""
    plan: list[str] = field(default_factory=list)
    plan_comments: list[str] = field(default_factory=list)
    current_step: int = 0
    completed_steps: list[int] = field(default_factory=list)
    partial_diff: str = ""
    halt_reason: str = ""
    branch_name: str = ""
    repo_path: str = ""
    pr_url: str = ""


class SessionManager:
    def __init__(self, state_path: str):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state: SessionState = self._load()

    def _load(self) -> SessionState:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                return SessionState(**data)
            except Exception as exc:
                logger.warning("Failed to load session state, starting fresh: %s", exc)
        return SessionState(task_id="")

    def save(self) -> None:
        self.state_path.write_text(json.dumps(asdict(self._state), indent=2))

    @property
    def state(self) -> SessionState:
        return self._state

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self._state, key, value)
        self.save()

    def reset(self) -> None:
        import uuid
        self._state = SessionState(task_id=str(uuid.uuid4()))
        self.save()
