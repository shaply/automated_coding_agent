"""
Phase 1 orchestrator: a plain while-loop state machine.

States:
  idle → planning → awaiting_plan_review → coding → awaiting_diff_review → done
                                                    ↘ halted (error / credits)

In Phase 3, this will be replaced by LangGraph for async FastAPI integration.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Callable

from orchestrator.session import SessionManager
from orchestrator.planner import Planner
from engine.base import CodingEngine

logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    max_self_correction_attempts: int = 3
    max_steps_per_session: int = 20


class Workflow:
    """
    Drives the full AutoDev task lifecycle.

    For Phase 1 (CLI), the review callbacks are simple input() prompts.
    In Phase 3+, these are replaced by FastAPI state transitions.
    """

    def __init__(
        self,
        session: SessionManager,
        planner: Planner,
        engine: CodingEngine,
        config: WorkflowConfig,
        # Callbacks — replaced by API endpoints in Phase 3
        review_plan_cb: Callable[[list[str]], tuple[bool, str | None]] | None = None,
        review_diff_cb: Callable[[str], bool] | None = None,
        log_cb: Callable[[str], None] | None = None,
    ):
        self.session = session
        self.planner = planner
        self.engine = engine
        self.config = config
        self._review_plan = review_plan_cb or self._cli_review_plan
        self._review_diff = review_diff_cb or self._cli_review_diff
        self._log = log_cb or (lambda msg: logger.info(msg))

    def run(self, task: str) -> None:
        task_id = str(uuid.uuid4())
        self.session.update(
            task_id=task_id,
            status="planning",
            task_description=task,
            plan=[],
            plan_comments=[],
            current_step=0,
            completed_steps=[],
            partial_diff="",
            halt_reason="",
        )
        self._log(f"[{task_id}] Starting task: {task}")

        # --- PLANNING PHASE ---
        plan = self.planner.generate_plan(task)
        self.session.update(status="awaiting_plan_review", plan=plan)
        self._log(f"Generated {len(plan)}-step plan.")

        while True:
            approved, comment = self._review_plan(plan)
            if approved:
                break
            if comment:
                self.session.state.plan_comments.append(comment)
                self._log(f"Refining plan based on comment: {comment}")
                plan = self.planner.refine_plan(plan, comment)
                self.session.update(plan=plan)

        self.session.update(status="coding")
        self._log("Plan approved. Starting implementation.")

        # --- IMPLEMENTATION LOOP ---
        steps = plan[: self.config.max_steps_per_session]
        for step_idx, step in enumerate(steps):
            self.session.update(current_step=step_idx)
            self._log(f"Step {step_idx + 1}/{len(steps)}: {step}")

            # Execute step — include all relevant files (Phase 1: pass empty list, let Aider decide)
            result = self.engine.execute_task(step, files=[])
            if not result.success:
                self._log(f"Step {step_idx + 1} failed: {result.error}")
                self.session.update(
                    status="halted",
                    halt_reason=f"Step {step_idx + 1} failed: {result.error}",
                )
                return

            self.session.state.completed_steps.append(step_idx)
            self.session.save()
            self._log(f"Step {step_idx + 1} complete.")

        # --- FINAL REVIEW ---
        diff = self.engine.get_diff()
        self.session.update(status="awaiting_diff_review", partial_diff=diff)
        self._log("Implementation complete. Awaiting final diff review.")

        approved = self._review_diff(diff)
        if approved:
            self.session.update(status="done")
            self._log("Diff approved. Task complete.")
        else:
            self.engine.reset()
            self.session.update(status="idle", halt_reason="Diff rejected by user.")
            self._log("Diff rejected. Changes discarded.")

    # --- CLI fallback callbacks (Phase 1 only) ---

    @staticmethod
    def _cli_review_plan(plan: list[str]) -> tuple[bool, str | None]:
        print("\n=== PLAN ===")
        for i, step in enumerate(plan):
            print(f"  {i + 1}. {step}")
        print()
        while True:
            choice = input("Approve plan? [y/n/comment]: ").strip()
            if choice.lower() == "y":
                return True, None
            if choice.lower() == "n":
                return False, None
            if choice:
                return False, choice

    @staticmethod
    def _cli_review_diff(diff: str) -> bool:
        print("\n=== DIFF ===")
        print(diff or "(no changes)")
        choice = input("\nApprove diff and push? [y/n]: ").strip().lower()
        return choice == "y"
