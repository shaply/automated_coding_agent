"""
FastAPI REST endpoints for AutoDev.

POST   /tasks                        → create a new task
GET    /tasks                        → list tasks (current session)
GET    /tasks/{id}                   → task detail + current state
GET    /tasks/{id}/plan              → fetch current plan
POST   /tasks/{id}/plan/comment      → request plan refinement with comment
POST   /tasks/{id}/plan/approve      → approve plan, start implementation
POST   /tasks/{id}/comment           → inject comment during implementation
GET    /tasks/{id}/diff              → get current unified diff
POST   /tasks/{id}/diff/approve      → approve diff → push branch + open PR
POST   /tasks/{id}/diff/reject       → discard changes
POST   /tasks/{id}/step-failure      → respond to step that hit correction cap
GET    /tasks/{id}/stream            → SSE live log stream (?token= for auth)
GET    /issues                       → list open GitHub issues assigned to agent
GET    /status                       → agent status
GET    /usage                        → daily token usage per provider
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import verify_token
from api.sse import make_sse_response

router = APIRouter(dependencies=[Depends(verify_token)])


# --- Request / Response models ---

class CreateTaskRequest(BaseModel):
    description: str
    issue_number: int | None = None


class CommentRequest(BaseModel):
    comment: str


class StepFailureRequest(BaseModel):
    choice: str  # "abort" | "skip" | "<comment to retry with>"


# --- Endpoints ---

@router.post("/tasks", status_code=202)
async def create_task(body: CreateTaskRequest):
    from main import app_state, run_workflow_async
    import asyncio
    session = app_state["session"]
    if session.state.status not in ("idle", "done", "halted", "halted:credits_exhausted"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Agent busy",
                "current_task": session.state.task_id,
                "state": session.state.status,
            },
        )
    session.reset()
    if body.issue_number is not None:
        session.update(issue_number=body.issue_number)
    asyncio.create_task(run_workflow_async(body.description, issue_number=body.issue_number))
    return {"task_id": session.state.task_id, "status": "accepted"}


@router.get("/tasks")
async def list_tasks():
    from main import app_state
    session = app_state["session"]
    return [_state_to_response(session.state)]


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    return _state_to_response(session.state)


@router.get("/tasks/{task_id}/plan")
async def get_plan(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    return {"plan": session.state.plan}


@router.post("/tasks/{task_id}/plan/comment")
async def add_plan_comment(task_id: str, body: CommentRequest):
    """Request plan refinement with a comment. Unblocks the workflow to re-plan."""
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_plan_review")
    session.state.plan_comments.append(body.comment)
    session.save()
    app_state["plan_comment"] = body.comment
    app_state["plan_action"] = "refine"
    app_state["plan_event"].set()
    return {"ok": True}


@router.post("/tasks/{task_id}/plan/approve")
async def approve_plan(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_plan_review")
    app_state["plan_action"] = "approve"
    app_state["plan_event"].set()
    return {"ok": True}


@router.post("/tasks/{task_id}/comment")
async def inject_comment(task_id: str, body: CommentRequest):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "coding")
    app_state["engine"].inject_comment(body.comment)
    return {"ok": True}


@router.get("/tasks/{task_id}/diff")
async def get_diff(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    return {"diff": session.state.partial_diff}


@router.post("/tasks/{task_id}/diff/approve")
async def approve_diff(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_diff_review")
    app_state["diff_action"] = "approve"
    app_state["diff_event"].set()
    return {"ok": True}


@router.post("/tasks/{task_id}/diff/reject")
async def reject_diff(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_diff_review")
    app_state["diff_action"] = "reject"
    app_state["diff_event"].set()
    return {"ok": True}


@router.post("/tasks/{task_id}/step-failure")
async def resolve_step_failure(task_id: str, body: StepFailureRequest):
    """
    Called when a step hits the self-correction cap.
    choice: "abort" | "skip" | "<comment to retry with>"
    """
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_step_review")
    app_state["step_failure_choice"] = body.choice
    app_state["step_failure_event"].set()
    return {"ok": True}


@router.get("/tasks/{task_id}/stream")
async def stream_logs(task_id: str):
    """SSE stream. Use ?token=<api_token> since EventSource can't send headers."""
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    return make_sse_response(task_id)


@router.get("/issues")
async def list_issues():
    """Return open GitHub issues assigned to the configured agent user."""
    from main import app_state, CONFIG
    github_client = app_state["github_client"]
    if github_client is None:
        raise HTTPException(status_code=503, detail="GitHub client not configured.")
    assignee = CONFIG["project"].get("github_assignee", "")
    if not assignee:
        raise HTTPException(status_code=503, detail="github_assignee not set in config.")
    issues = github_client.get_assigned_issues(assignee)
    return {
        "issues": [
            {"number": i.number, "title": i.title, "body": i.body, "url": i.url, "labels": i.labels}
            for i in issues
        ]
    }


@router.get("/status")
async def get_status():
    from main import app_state
    session = app_state["session"]
    return {"status": session.state.status, "task_id": session.state.task_id}


@router.get("/usage")
async def get_usage():
    from main import app_state
    usage_db = app_state["usage_db"]
    return {"usage": usage_db.get_all_usage()}


# --- Helpers ---

def _state_to_response(state) -> dict:
    return {
        "task_id": state.task_id,
        "status": state.status,
        "description": state.task_description,
        "plan": state.plan,
        "current_step": state.current_step,
        "branch_name": state.branch_name,
        "pr_url": state.pr_url,
        "halt_reason": state.halt_reason,
        "step_failure_info": state.step_failure_info,
        "issue_number": state.issue_number,
    }


def _assert_task(session, task_id: str) -> None:
    if session.state.task_id != task_id:
        raise HTTPException(status_code=404, detail="Task not found.")


def _assert_status(session, expected: str) -> None:
    if session.state.status != expected:
        raise HTTPException(
            status_code=409,
            detail=f"Expected status '{expected}', got '{session.state.status}'.",
        )
