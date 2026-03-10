"""
FastAPI REST endpoints for AutoDev.

Designed to be called by the Svelte UI today and by RoboMesh in Phase 8 —
the API surface stays the same regardless of who's calling.

POST   /tasks                   → create a new task
GET    /tasks                   → list all tasks
GET    /tasks/{id}              → task detail + current state
GET    /tasks/{id}/plan         → fetch current plan
POST   /tasks/{id}/plan/comment → add comment to plan
POST   /tasks/{id}/plan/approve → approve plan, start implementation
POST   /tasks/{id}/comment      → inject comment during implementation
GET    /tasks/{id}/diff         → get current unified diff
POST   /tasks/{id}/diff/approve → approve diff → push branch + open PR
POST   /tasks/{id}/diff/reject  → discard changes, wipe temp dir
GET    /status                  → agent status
GET    /usage                   → daily token usage per provider
GET    /tasks/{id}/stream       → SSE live log stream
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import verify_token
from api.sse import make_sse_response

# These will be injected by main.py via dependency overrides or app state
router = APIRouter(dependencies=[Depends(verify_token)])


# --- Request / Response models ---

class CreateTaskRequest(BaseModel):
    description: str


class CommentRequest(BaseModel):
    comment: str


class TaskResponse(BaseModel):
    task_id: str
    status: str
    description: str
    plan: list[str]
    current_step: int
    branch_name: str
    pr_url: str
    halt_reason: str


# --- Endpoints ---

@router.post("/tasks", status_code=202)
async def create_task(body: CreateTaskRequest):
    from main import app_state
    session = app_state["session"]
    if session.state.status not in ("idle", "done"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Agent busy",
                "current_task": session.state.task_id,
                "state": session.state.status,
            },
        )
    # Trigger workflow asynchronously (Phase 3 will use LangGraph / background task)
    import asyncio
    from main import run_workflow_async
    task = asyncio.create_task(run_workflow_async(body.description))
    return {"task_id": session.state.task_id, "status": "accepted"}


@router.get("/tasks")
async def list_tasks():
    from main import app_state
    session = app_state["session"]
    state = session.state
    return [_state_to_response(state)]


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    from main import app_state
    session = app_state["session"]
    if session.state.task_id != task_id:
        raise HTTPException(status_code=404, detail="Task not found.")
    return _state_to_response(session.state)


@router.get("/tasks/{task_id}/plan")
async def get_plan(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    return {"plan": session.state.plan}


@router.post("/tasks/{task_id}/plan/comment")
async def add_plan_comment(task_id: str, body: CommentRequest):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_plan_review")
    session.state.plan_comments.append(body.comment)
    session.save()
    return {"ok": True}


@router.post("/tasks/{task_id}/plan/approve")
async def approve_plan(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_plan_review")
    # Signal the waiting workflow
    app_state["plan_approved"].set()
    return {"ok": True}


@router.post("/tasks/{task_id}/comment")
async def inject_comment(task_id: str, body: CommentRequest):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "coding")
    engine = app_state["engine"]
    engine.inject_comment(body.comment)
    return {"ok": True}


@router.get("/tasks/{task_id}/diff")
async def get_diff(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    diff = session.state.partial_diff
    return {"diff": diff}


@router.post("/tasks/{task_id}/diff/approve")
async def approve_diff(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_diff_review")
    app_state["diff_approved"].set()
    return {"ok": True}


@router.post("/tasks/{task_id}/diff/reject")
async def reject_diff(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    _assert_status(session, "awaiting_diff_review")
    app_state["diff_rejected"].set()
    return {"ok": True}


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


@router.get("/tasks/{task_id}/stream")
async def stream_logs(task_id: str):
    from main import app_state
    session = app_state["session"]
    _assert_task(session, task_id)
    return make_sse_response(task_id)


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
