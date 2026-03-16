"""
Phase 1+2 orchestrator: a plain while-loop state machine.

States:
  idle → planning → awaiting_plan_review → coding → awaiting_diff_review → done
                                                    ↘ halted (error / credits)

Phase 2 adds:
  - Linter + test runner after every implementation step
  - Self-correction loop: AI fixes its own failures before surfacing to you
  - max_self_correction_attempts cap per step

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

# Sentinel returned by the step-failure callback when the user wants to abort.
_ABORT = "abort"
_SKIP = "skip"


@dataclass
class WorkflowConfig:
    max_self_correction_attempts: int = 3
    max_steps_per_session: int = 20
    run_tests: bool = True  # Phase 2: set False to skip test execution (e.g. no test suite yet)


class Workflow:
    """
    Drives the full AutoDev task lifecycle.

    For Phase 1+2 (CLI), the review callbacks are simple input() prompts.
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
        step_failure_cb: Callable[[int, str, str], str] | None = None,
        log_cb: Callable[[str], None] | None = None,
    ):
        self.session = session
        self.planner = planner
        self.engine = engine
        self.config = config
        self._review_plan = review_plan_cb or self._cli_review_plan
        self._review_diff = review_diff_cb or self._cli_review_diff
        # Called when self-correction cap is hit: (step_idx, step_desc, test_output) → "abort"|"skip"|<comment>
        self._on_step_failure = step_failure_cb or self._cli_step_failure
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
            step_test_results=[],
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

        # --- IMPLEMENTATION LOOP (Phase 2: with self-correction) ---
        steps = plan[: self.config.max_steps_per_session]
        for step_idx, step in enumerate(steps):
            self.session.update(current_step=step_idx)
            self._log(f"Step {step_idx + 1}/{len(steps)}: {step}")

            if not self._run_step_with_correction(step_idx, step, len(steps)):
                return  # halted or aborted

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

    # -------------------------------------------------------------------------
    # Phase 2: self-correction loop
    # -------------------------------------------------------------------------

    def _run_step_with_correction(self, step_idx: int, step: str, total_steps: int) -> bool:
        """
        Execute one plan step, then run tests and self-correct on failure.

        Returns True if the step completed successfully (or was skipped by user),
        False if the workflow should halt.
        """
        # Execute the step (agent implements the code change)
        result = self.engine.execute_task(step, files=[])
        if not result.success:
            self._log(f"Step {step_idx + 1} failed to execute: {result.error}")
            self.session.update(
                status="halted",
                halt_reason=f"Step {step_idx + 1} execution failed: {result.error}",
            )
            return False

        if not self.config.run_tests:
            # Tests disabled — treat as passing
            self._record_test(step_idx, attempt=0, passed=True, output="(tests disabled)")
            self._log(f"Step {step_idx + 1}/{total_steps} complete (tests skipped).")
            self.session.state.completed_steps.append(step_idx)
            self.session.save()
            return True

        # Self-correction loop
        for attempt in range(self.config.max_self_correction_attempts + 1):
            test_result = self.engine.run_tests()
            self._record_test(step_idx, attempt, test_result.passed, test_result.output)

            if test_result.passed:
                self._log(
                    f"Step {step_idx + 1}/{total_steps} complete"
                    + (f" (self-corrected in {attempt} attempt(s))" if attempt > 0 else "")
                    + "."
                )
                self.session.state.completed_steps.append(step_idx)
                self.session.save()
                return True

            # Tests failed
            if attempt < self.config.max_self_correction_attempts:
                self._log(
                    f"Tests failed on step {step_idx + 1} (attempt {attempt + 1}/"
                    f"{self.config.max_self_correction_attempts}). Self-correcting…"
                )
                correction_prompt = (
                    f"The tests/linter failed after implementing: '{step}'\n\n"
                    f"Test output:\n{test_result.output}\n\n"
                    "Please fix the issues above. Do not change anything unrelated to the failure."
                )
                self.engine.inject_comment(correction_prompt)
            else:
                # Self-correction cap hit — surface to user
                self._log(
                    f"Self-correction cap reached for step {step_idx + 1} "
                    f"({self.config.max_self_correction_attempts} attempts). Surfacing to user."
                )
                choice = self._on_step_failure(step_idx, step, test_result.output)

                if choice == _ABORT:
                    self.session.update(
                        status="halted",
                        halt_reason=(
                            f"Step {step_idx + 1} could not be corrected after "
                            f"{self.config.max_self_correction_attempts} attempts. Aborted by user."
                        ),
                    )
                    return False
                elif choice == _SKIP:
                    self._log(f"Step {step_idx + 1} skipped by user.")
                    self.session.state.completed_steps.append(step_idx)
                    self.session.save()
                    return True
                else:
                    # User injected a new approach — inject it and try one more time
                    self._log(f"User injected new approach for step {step_idx + 1}: {choice}")
                    self.engine.inject_comment(choice)
                    test_result = self.engine.run_tests()
                    self._record_test(step_idx, attempt + 1, test_result.passed, test_result.output)
                    if test_result.passed:
                        self._log(f"Step {step_idx + 1} succeeded after user injection.")
                        self.session.state.completed_steps.append(step_idx)
                        self.session.save()
                        return True
                    else:
                        self._log(f"Step {step_idx + 1} still failing after user injection. Halting.")
                        self.session.update(
                            status="halted",
                            halt_reason=f"Step {step_idx + 1} still failing after user intervention.",
                        )
                        return False

        # Unreachable, but satisfies type checker
        return False

    def _record_test(self, step: int, attempt: int, passed: bool, output: str) -> None:
        self.session.state.step_test_results.append(
            {"step": step, "attempt": attempt, "passed": passed, "output": output}
        )

    # -------------------------------------------------------------------------
    # CLI fallback callbacks
    # -------------------------------------------------------------------------

    @staticmethod
    def _cli_review_plan(plan: list[str]) -> tuple[bool, str | None]:
        print("\n=== PLAN ===")
        for i, step in enumerate(plan):
            print(f"  {i + 1}. {step}")
        print()
        while True:
            choice = input("Approve plan? [y=approve / n=reject / <comment>=refine]: ").strip()
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

    @staticmethod
    def _cli_step_failure(step_idx: int, step: str, test_output: str) -> str:
        print(f"\n=== STEP {step_idx + 1} SELF-CORRECTION FAILED ===")
        print(f"Step: {step}")
        print(f"\nTest output:\n{test_output}")
        print("\nOptions:")
        print("  abort  — halt the task entirely")
        print("  skip   — skip this step and continue")
        print("  <text> — inject a new approach and try once more")
        choice = input("Choice: ").strip()
        return choice if choice else _ABORT
