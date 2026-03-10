"""Tests for orchestrator/workflow.py (Phase 1 + Phase 2)."""

import pytest
from unittest.mock import MagicMock, patch
from orchestrator.workflow import Workflow, WorkflowConfig, _ABORT, _SKIP
from orchestrator.session import SessionManager
from engine.result import EngineResult, TestResult


def _make_mock_engine(
    execute_success=True,
    execute_error=None,
    diff="--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new",
    tests_pass=True,
    test_output="1 passed",
):
    engine = MagicMock()
    engine.execute_task.return_value = EngineResult(
        success=execute_success,
        diff=diff,
        files_changed=[],
        error=execute_error,
    )
    engine.get_diff.return_value = diff
    engine.run_tests.return_value = TestResult(passed=tests_pass, output=test_output)
    return engine


def _make_mock_planner(plan=None):
    planner = MagicMock()
    planner.generate_plan.return_value = plan or ["Step 1: do the thing", "Step 2: test it"]
    planner.refine_plan.return_value = plan or ["Step 1: do the thing", "Step 2: test it"]
    return planner


def _make_workflow(
    session_path,
    engine=None,
    planner=None,
    plan=None,
    max_corrections=2,
    run_tests=True,
    approve_plan=True,
    approve_diff=True,
    step_failure_response=_ABORT,
):
    session = SessionManager(session_path)
    eng = engine or _make_mock_engine()
    pln = planner or _make_mock_planner(plan)

    config = WorkflowConfig(
        max_self_correction_attempts=max_corrections,
        max_steps_per_session=20,
        run_tests=run_tests,
    )

    wf = Workflow(
        session=session,
        planner=pln,
        engine=eng,
        config=config,
        review_plan_cb=lambda p: (approve_plan, None),
        review_diff_cb=lambda d: approve_diff,
        step_failure_cb=lambda idx, step, out: step_failure_response,
        log_cb=lambda msg: None,
    )
    return wf, session, eng, pln


# ---------------------------------------------------------------------------
# Phase 1: basic workflow
# ---------------------------------------------------------------------------

class TestPhase1Workflow:
    def test_full_happy_path(self, session_path):
        wf, session, engine, _ = _make_workflow(session_path, run_tests=False)
        wf.run("Add a login button")

        assert session.state.status == "done"
        engine.execute_task.assert_called()
        assert len(session.state.completed_steps) == 2  # plan has 2 steps

    def test_status_transitions(self, session_path):
        statuses = []
        session = SessionManager(session_path)
        planner = _make_mock_planner()
        engine = _make_mock_engine()
        config = WorkflowConfig(run_tests=False)

        def log_cb(msg):
            statuses.append(session.state.status)

        wf = Workflow(
            session=session, planner=planner, engine=engine, config=config,
            review_plan_cb=lambda p: (True, None),
            review_diff_cb=lambda d: True,
            log_cb=log_cb,
        )
        wf.run("task")
        assert "planning" in statuses
        assert session.state.status == "done"

    def test_diff_reject_resets_engine(self, session_path):
        wf, session, engine, _ = _make_workflow(
            session_path, run_tests=False, approve_diff=False
        )
        wf.run("task")
        engine.reset.assert_called_once()
        assert session.state.status == "idle"

    def test_execute_failure_halts(self, session_path):
        engine = _make_mock_engine(execute_success=False, execute_error="syntax error")
        wf, session, _, _ = _make_workflow(session_path, engine=engine, run_tests=False)
        wf.run("task")
        assert session.state.status == "halted"
        assert "syntax error" in session.state.halt_reason

    def test_plan_refinement_loop(self, session_path):
        session = SessionManager(session_path)
        planner = _make_mock_planner()
        engine = _make_mock_engine()
        config = WorkflowConfig(run_tests=False)

        call_count = 0
        def review_cb(plan):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, "make it simpler"
            return True, None

        wf = Workflow(
            session=session, planner=planner, engine=engine, config=config,
            review_plan_cb=review_cb,
            review_diff_cb=lambda d: True,
            log_cb=lambda msg: None,
        )
        wf.run("task")

        planner.refine_plan.assert_called_once()
        assert session.state.status == "done"

    def test_task_id_is_set(self, session_path):
        wf, session, _, _ = _make_workflow(session_path, run_tests=False)
        wf.run("task")
        assert session.state.task_id != ""


# ---------------------------------------------------------------------------
# Phase 2: self-correction loop
# ---------------------------------------------------------------------------

class TestPhase2SelfCorrection:
    def test_passing_tests_complete_step(self, session_path):
        engine = _make_mock_engine(tests_pass=True)
        wf, session, eng, _ = _make_workflow(session_path, engine=engine)
        wf.run("task")

        assert session.state.status == "done"
        assert len(session.state.step_test_results) == 2  # 2 steps, each 1 test run

    def test_failing_tests_trigger_self_correction(self, session_path):
        """Tests fail twice then pass — agent should self-correct."""
        engine = MagicMock()
        engine.execute_task.return_value = EngineResult(success=True, diff="", files_changed=[])
        engine.get_diff.return_value = ""

        call_count = 0
        def run_tests_side_effect():
            nonlocal call_count
            call_count += 1
            # Fail on first 2 calls per step, pass on 3rd
            return TestResult(passed=(call_count % 3 == 0), output="fail" if call_count % 3 != 0 else "ok")

        engine.run_tests.side_effect = run_tests_side_effect

        wf, session, eng, _ = _make_workflow(session_path, engine=engine, max_corrections=3)
        wf.run("one step task")

        # inject_comment should have been called to self-correct
        assert eng.inject_comment.called

    def test_self_correction_cap_abort(self, session_path):
        """When cap is hit and user aborts, workflow halts."""
        engine = _make_mock_engine(tests_pass=False, test_output="tests failed")
        wf, session, _, _ = _make_workflow(
            session_path, engine=engine, max_corrections=2,
            step_failure_response=_ABORT,
        )
        wf.run("task")

        assert session.state.status == "halted"
        assert "could not be corrected" in session.state.halt_reason

    def test_self_correction_cap_skip(self, session_path):
        """When cap is hit and user skips, step is marked done and workflow continues."""
        engine = _make_mock_engine(tests_pass=False)
        wf, session, _, _ = _make_workflow(
            session_path, engine=engine, max_corrections=1,
            step_failure_response=_SKIP,
        )
        wf.run("two step task")

        # Both steps skipped, workflow reaches diff review
        assert session.state.status in ("done", "awaiting_diff_review")

    def test_test_results_recorded_in_session(self, session_path):
        engine = _make_mock_engine(tests_pass=True)
        wf, session, _, _ = _make_workflow(session_path, engine=engine)
        wf.run("task")

        assert len(session.state.step_test_results) > 0
        for r in session.state.step_test_results:
            assert "step" in r
            assert "passed" in r
            assert "output" in r

    def test_tests_disabled_skips_test_runner(self, session_path):
        engine = _make_mock_engine()
        wf, session, eng, _ = _make_workflow(session_path, engine=engine, run_tests=False)
        wf.run("task")

        eng.run_tests.assert_not_called()
        assert session.state.status == "done"

    def test_user_injection_on_cap_hit(self, session_path):
        """User injects a fix approach instead of aborting/skipping."""
        # Tests fail → cap hit → user injects → test now passes
        engine = MagicMock()
        engine.execute_task.return_value = EngineResult(success=True, diff="", files_changed=[])
        engine.get_diff.return_value = ""

        run_count = 0
        def run_tests():
            nonlocal run_count
            run_count += 1
            # Always fail until inject is called, then pass
            return TestResult(passed=(engine.inject_comment.called), output="fail")

        engine.run_tests.side_effect = run_tests

        wf, session, eng, _ = _make_workflow(
            session_path, engine=engine, max_corrections=1,
            step_failure_response="try using a different approach",
        )

        # Override run_tests to pass after inject
        engine.run_tests.side_effect = [
            TestResult(passed=False, output="fail"),  # initial
            TestResult(passed=False, output="fail"),  # correction attempt 1
            TestResult(passed=True, output="ok"),     # after user injection
            TestResult(passed=True, output="ok"),     # step 2
        ]

        wf.run("task")
        eng.inject_comment.assert_called()
