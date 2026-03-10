"""Tests for orchestrator/session.py"""

import json
import pytest
from orchestrator.session import SessionManager, SessionState


def test_session_starts_empty(session_path):
    mgr = SessionManager(session_path)
    assert mgr.state.task_id == ""
    assert mgr.state.status == "idle"
    assert mgr.state.plan == []


def test_session_update_persists(session_path):
    mgr = SessionManager(session_path)
    mgr.update(task_id="abc", status="planning", task_description="fix bug")

    # Load fresh instance from same path
    mgr2 = SessionManager(session_path)
    assert mgr2.state.task_id == "abc"
    assert mgr2.state.status == "planning"
    assert mgr2.state.task_description == "fix bug"


def test_session_update_plan(session_path):
    mgr = SessionManager(session_path)
    mgr.update(plan=["step1", "step2"])
    assert mgr.state.plan == ["step1", "step2"]


def test_session_step_test_results(session_path):
    mgr = SessionManager(session_path)
    mgr.state.step_test_results.append({"step": 0, "attempt": 0, "passed": True, "output": "OK"})
    mgr.save()

    mgr2 = SessionManager(session_path)
    assert len(mgr2.state.step_test_results) == 1
    assert mgr2.state.step_test_results[0]["passed"] is True


def test_session_reset_generates_new_id(session_path):
    mgr = SessionManager(session_path)
    mgr.update(task_id="old-id", status="coding")
    mgr.reset()

    assert mgr.state.task_id != "old-id"
    assert mgr.state.status == "idle"


def test_session_handles_corrupt_file(session_path):
    """Corrupt JSON should be silently ignored — start fresh."""
    with open(session_path, "w") as f:
        f.write("{not valid json}")

    mgr = SessionManager(session_path)
    assert mgr.state.task_id == ""


def test_session_file_created_in_nonexistent_dir(tmp_path):
    path = str(tmp_path / "nested" / "dir" / "session.json")
    mgr = SessionManager(path)
    mgr.update(task_id="x")
    mgr2 = SessionManager(path)
    assert mgr2.state.task_id == "x"
