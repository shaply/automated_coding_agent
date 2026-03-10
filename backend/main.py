"""
AutoDev backend entry point.

Phase 1: FastAPI app + APScheduler + plain while-loop workflow.
Phase 3: This becomes a full LangGraph-backed async service.

Run locally:
    python main.py

Or via uvicorn:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import uvicorn
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from engine.aider_engine import AiderEngine
from integrations.llm_client import LLMClient
from integrations.usage_db import UsageDB
from orchestrator.planner import Planner
from orchestrator.session import SessionManager
from orchestrator.workflow import Workflow, WorkflowConfig

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


CONFIG = load_config()

# ---------------------------------------------------------------------------
# Shared application state (injected into routes via app_state global)
# ---------------------------------------------------------------------------

DATA_DIR = os.environ.get("AUTODEV_DATA_DIR", "/data")

usage_db = UsageDB(
    db_path=f"{DATA_DIR}/usage.db",
    timezone=CONFIG["schedule"]["timezone"],
)

session = SessionManager(state_path=f"{DATA_DIR}/session.json")

llm = LLMClient(
    providers_config=CONFIG["providers"],
    fallback_order=CONFIG["providers"]["fallback_order"],
    usage_db=usage_db,
)

engine = AiderEngine(
    model_name=CONFIG["providers"][CONFIG["providers"]["fallback_order"][0]]["model"],
    repo_path="",  # set per-task at runtime
    test_command=CONFIG["project"].get("test_command", "pytest"),
    lint_command=CONFIG["project"].get("lint_command", "ruff check ."),
)

planner = Planner(llm=llm, repo_path="")  # repo_path set per-task

# asyncio events for API→workflow signalling (Phase 1 approach; replaced by LangGraph in Ph3)
app_state = {
    "session": session,
    "usage_db": usage_db,
    "engine": engine,
    "planner": planner,
    "plan_approved": asyncio.Event(),
    "diff_approved": asyncio.Event(),
    "diff_rejected": asyncio.Event(),
}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="AutoDev", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# ---------------------------------------------------------------------------
# Workflow runner (called by POST /tasks and APScheduler)
# ---------------------------------------------------------------------------

async def run_workflow_async(task: str) -> None:
    """Run the workflow in an asyncio-friendly way (blocking calls in thread pool)."""
    loop = asyncio.get_event_loop()

    workflow_config = WorkflowConfig(
        max_self_correction_attempts=CONFIG["agent"]["max_self_correction_attempts"],
        max_steps_per_session=CONFIG["agent"]["max_steps_per_session"],
    )

    def _log(msg: str) -> None:
        logger.info(msg)
        from api.sse import publish_log
        publish_log(session.state.task_id, msg)

    workflow = Workflow(
        session=session,
        planner=planner,
        engine=engine,
        config=workflow_config,
        log_cb=_log,
    )

    try:
        await loop.run_in_executor(None, workflow.run, task)
    except Exception as exc:
        logger.exception("Workflow crashed: %s", exc)
        session.update(status="halted", halt_reason=str(exc))
    finally:
        from api.sse import close_stream
        close_stream(session.state.task_id)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

scheduler = AsyncIOScheduler(timezone=CONFIG["schedule"]["timezone"])


async def scheduled_run() -> None:
    if session.state.status not in ("idle", "done"):
        logger.info(
            "Scheduled run skipped — task %s already in progress (status: %s)",
            session.state.task_id,
            session.state.status,
        )
        return
    logger.info("Scheduler triggered — starting automated run.")
    # Automated run: pull task from GitHub issues (Phase 5). For now, skip if no task provided.
    logger.info("No automated task source configured. Scheduler run skipped.")


@app.on_event("startup")
async def startup() -> None:
    if CONFIG["schedule"]["enabled"]:
        run_time = CONFIG["schedule"]["time"]
        hour, minute = run_time.split(":")
        scheduler.add_job(scheduled_run, "cron", hour=int(hour), minute=int(minute))
        scheduler.start()
        logger.info("Scheduler started — daily run at %s %s", run_time, CONFIG["schedule"]["timezone"])


@app.on_event("shutdown")
async def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    usage_db.close()


# ---------------------------------------------------------------------------
# CLI entry point (Phase 1 only — run without Docker / uvicorn)
# ---------------------------------------------------------------------------

def cli_run() -> None:
    """Run a single task interactively from the command line."""
    if len(sys.argv) < 2:
        print("Usage: python main.py '<task description>'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    print(f"AutoDev CLI — task: {task}\n")

    workflow_config = WorkflowConfig(
        max_self_correction_attempts=CONFIG["agent"]["max_self_correction_attempts"],
        max_steps_per_session=CONFIG["agent"]["max_steps_per_session"],
    )

    workflow = Workflow(
        session=session,
        planner=planner,
        engine=engine,
        config=workflow_config,
    )
    workflow.run(task)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        cli_run()
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
