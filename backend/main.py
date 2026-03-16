"""
AutoDev backend entry point — Phase 3/4/5.

Architecture:
  - Workflow runs in a thread pool executor (blocking code off the event loop)
  - threading.Events bridge the API layer → workflow callbacks
  - Ephemeral repo clone per task in /tmp/autodev-task-{id}/
  - Git safety check on every task start
  - GitHub integration: fetch issues, push branch, open PR on approval

Run locally:
    python main.py

Or via uvicorn:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
import logging.handlers
import os
import shutil
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from engine.aider_engine import AiderEngine
from integrations.git_client import GitClient, GitSafetyError
from integrations.github_client import GitHubClient
from integrations.llm_client import LLMClient
from integrations.usage_db import UsageDB
from orchestrator.planner import Planner
from orchestrator.session import SessionManager
from orchestrator.workflow import Workflow, WorkflowConfig

load_dotenv()

# ---------------------------------------------------------------------------
# Logging — console + rotating file at /data/autodev.log
# ---------------------------------------------------------------------------

_LOG_FMT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATA_DIR_EARLY = os.environ.get("AUTODEV_DATA_DIR", "/data")
Path(_DATA_DIR_EARLY).mkdir(parents=True, exist_ok=True)

_file_handler = logging.handlers.RotatingFileHandler(
    filename=f"{_DATA_DIR_EARLY}/autodev.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB per file
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(_LOG_FMT))

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FMT,
    handlers=[logging.StreamHandler(), _file_handler],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


CONFIG = load_config()
DATA_DIR = os.environ.get("AUTODEV_DATA_DIR", "/data")


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

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

# Engine and planner — repo_path is set per-task before the workflow starts
engine = AiderEngine(
    model_name=CONFIG["providers"][CONFIG["providers"]["fallback_order"][0]]["model"],
    repo_path="",
    test_command=CONFIG["project"].get("test_command", "pytest"),
    lint_command=CONFIG["project"].get("lint_command", "ruff check ."),
)

planner = Planner(llm=llm, repo_path="")

# GitHub client — optional; only created when credentials are present
_github_token = os.environ.get("GITHUB_TOKEN", "")
_github_repo = CONFIG["project"].get("github_repo", "")
github_client: GitHubClient | None = None
if _github_token and _github_repo:
    try:
        github_client = GitHubClient(token=_github_token, repo_name=_github_repo)
        logger.info("GitHub client initialised for %s", _github_repo)
    except Exception as exc:
        logger.warning("GitHub client failed to initialise: %s", exc)

git_client = GitClient(
    remote_url=f"https://{_github_token}@github.com/{_github_repo}.git" if _github_token and _github_repo else "",
    base_branch=CONFIG["project"].get("base_branch", "main"),
)

# ---------------------------------------------------------------------------
# Inter-thread signalling (API → blocked workflow thread)
# threading.Event is required here — the workflow runs in a thread pool, not
# the asyncio event loop, so asyncio.Event cannot be used.
# ---------------------------------------------------------------------------

def _fresh_events() -> dict:
    return {
        # Plan review
        "plan_event": threading.Event(),
        "plan_action": None,    # "approve" | "refine"
        "plan_comment": "",
        # Diff review
        "diff_event": threading.Event(),
        "diff_action": None,    # "approve" | "reject"
        # Step failure (self-correction cap hit)
        "step_failure_event": threading.Event(),
        "step_failure_choice": "abort",  # "abort" | "skip" | <comment>
    }


app_state = {
    "session": session,
    "usage_db": usage_db,
    "engine": engine,
    "planner": planner,
    "github_client": github_client,
    "git_client": git_client,
    **_fresh_events(),
}


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

scheduler = AsyncIOScheduler(timezone=CONFIG["schedule"]["timezone"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    # If the server restarted mid-task, no workflow thread will resume it.
    # Mark any in-progress states as halted so the UI doesn't get stuck.
    _stale = {"planning", "awaiting_plan_review", "coding", "awaiting_step_review", "awaiting_diff_review"}
    if session.state.status in _stale:
        session.update(status="halted", halt_reason="Server restarted while task was in progress.")
        logger.warning("Stale session detected on startup — marked as halted.")

    if CONFIG["schedule"]["enabled"]:
        run_time = CONFIG["schedule"]["time"]
        hour, minute = run_time.split(":")
        scheduler.add_job(scheduled_run, "cron", hour=int(hour), minute=int(minute), id="scheduled_run")
        scheduler.start()
        logger.info(
            "Scheduler started — daily run at %s %s",
            run_time, CONFIG["schedule"]["timezone"],
        )
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    usage_db.close()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="AutoDev", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ---------------------------------------------------------------------------
# Workflow runner
# ---------------------------------------------------------------------------

async def run_workflow_async(task: str, issue_number: int | None = None) -> None:
    """
    Run the full task lifecycle:
      1. Clone repo into ephemeral temp dir
      2. Git safety check
      3. Create feature branch
      4. Run workflow (plan → review → code → review → push/PR)
      5. Clean up temp dir
    """
    from api.sse import publish_log, close_stream

    # Reset signalling events for the new task
    events = _fresh_events()
    app_state.update(events)

    task_id = session.state.task_id  # already set by POST /tasks
    repo_path: str | None = None

    def _log(msg: str) -> None:
        logger.info(msg)
        publish_log(task_id, msg)

    # -- 1. Clone repo ---------------------------------------------------
    repo = None  # may remain None in local mode
    if git_client.remote_url:
        _log(f"Cloning {_github_repo} …")
        try:
            repo, clone_path = await asyncio.get_event_loop().run_in_executor(
                None, git_client.clone_ephemeral, task_id
            )
            repo_path = str(clone_path)
        except Exception as exc:
            _log(f"Clone failed: {exc}")
            session.update(status="halted", halt_reason=f"Clone failed: {exc}")
            close_stream(task_id)
            return
    else:
        _log("No GitHub repo configured — working in local mode (no clone).")

    # -- 2. Git safety check + feature branch ----------------------------
    if repo_path:
        branch_name = (
            f"autodev/issue-{issue_number}" if issue_number
            else f"autodev/task-{task_id[:8]}"
        )
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: _setup_branch(repo, repo_path, branch_name)
            )
            session.update(branch_name=branch_name, repo_path=repo_path)
            _log(f"Feature branch: {branch_name}")
        except GitSafetyError as exc:
            _log(f"Git safety check failed: {exc}")
            session.update(status="halted", halt_reason=str(exc))
            close_stream(task_id)
            _cleanup(repo_path)
            return

        # Point engine and planner at the cloned repo
        engine.repo_path = Path(repo_path)
        planner.repo_path = repo_path

    # -- 3. Build blocking callbacks (safe to block — we're in a thread) --

    def _review_plan_cb(_: list[str]) -> tuple[bool, str | None]:
        while True:
            app_state["plan_event"].wait()
            app_state["plan_event"].clear()
            action = app_state["plan_action"]
            if action == "approve":
                return True, None
            if action == "refine":
                return False, app_state["plan_comment"]

    def _review_diff_cb(_: str) -> bool:
        app_state["diff_event"].wait()
        app_state["diff_event"].clear()
        return app_state["diff_action"] == "approve"

    def _step_failure_cb(step_idx: int, step: str, test_output: str) -> str:
        session.update(
            status="awaiting_step_review",
            step_failure_info={"step": step_idx, "description": step, "output": test_output},
        )
        app_state["step_failure_event"].wait()
        app_state["step_failure_event"].clear()
        session.update(status="coding")
        return app_state["step_failure_choice"]

    # -- 4. Run workflow --------------------------------------------------
    workflow_config = WorkflowConfig(
        max_self_correction_attempts=CONFIG["agent"]["max_self_correction_attempts"],
        max_steps_per_session=CONFIG["agent"]["max_steps_per_session"],
        run_tests=CONFIG["project"].get("run_tests", True),
    )

    workflow = Workflow(
        session=session,
        planner=planner,
        engine=engine,
        config=workflow_config,
        review_plan_cb=_review_plan_cb,
        review_diff_cb=_review_diff_cb,
        step_failure_cb=_step_failure_cb,
        log_cb=_log,
    )

    try:
        await asyncio.get_event_loop().run_in_executor(None, workflow.run, task)
    except Exception as exc:
        logger.exception("Workflow crashed: %s", exc)
        session.update(status="halted", halt_reason=str(exc))
        close_stream(task_id)
        _cleanup(repo_path)
        return

    # -- 5. Commit changes, push branch + open PR (if approved) ----------
    final_status = session.state.status
    if final_status == "done" and repo is not None and repo_path and git_client.remote_url:
        commit_msg = f"[AutoDev] {task[:60]}"
        _repo = repo  # capture for lambda — repo is not None here
        committed = await asyncio.get_event_loop().run_in_executor(
            None, lambda: git_client.commit_all(_repo, commit_msg)
        )
        if not committed:
            _log("WARNING: No file changes were made — nothing to commit. Skipping push and PR.")
            close_stream(task_id)
            _cleanup(repo_path)
            return

        _log("Pushing branch …")
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: git_client.push_branch(_repo, session.state.branch_name)
            )
            _log(f"Branch pushed: {session.state.branch_name}")
        except Exception as exc:
            _log(f"Push failed: {exc}")

        _gh = github_client  # narrow away None for type checker
        if _gh is not None:
            try:
                pr_title = _pr_title(task, issue_number)
                pr_body_text = _pr_body(session.state, issue_number)
                pr_url = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _gh.open_pull_request(
                        branch=session.state.branch_name,
                        title=pr_title,
                        body=pr_body_text,
                        base=CONFIG["project"].get("base_branch", "main"),
                    ),
                )
                session.update(pr_url=pr_url)
                _log(f"PR opened: {pr_url}")
            except Exception as exc:
                _log(f"PR creation failed: {exc}")

    close_stream(task_id)
    _cleanup(repo_path)


def _setup_branch(repo, _: str, branch_name: str) -> None:
    """Create feature branch on a fresh clone (nothing to pull)."""
    git_client.create_feature_branch(repo, branch_name)


def _cleanup(repo_path: str | None) -> None:
    if repo_path and Path(repo_path).exists():
        shutil.rmtree(repo_path, ignore_errors=True)
        logger.info("Wiped ephemeral repo: %s", repo_path)


def _pr_title(task: str, issue_number: int | None) -> str:
    prefix = f"[AutoDev] Fix #{issue_number}: " if issue_number else "[AutoDev] "
    return (prefix + task)[:72]


def _pr_body(state, issue_number: int | None) -> str:
    steps = "\n".join(f"- {s}" for s in state.plan)
    issue_ref = f"\nCloses #{issue_number}" if issue_number else ""
    return (
        f"## Summary\nAutomatically generated by AutoDev.\n\n"
        f"**Task:** {state.task_description}\n\n"
        f"## Plan\n{steps}\n{issue_ref}\n\n"
        f"---\n*Review the diff carefully before merging.*"
    )


async def scheduled_run() -> None:
    if session.state.status not in ("idle", "done"):
        logger.info(
            "Scheduled run skipped — task %s in progress (status: %s)",
            session.state.task_id, session.state.status,
        )
        return

    if not github_client:
        logger.info("Scheduler: no GitHub client configured, skipping.")
        return

    assignee = CONFIG["project"].get("github_assignee", "")
    if not assignee:
        logger.info("Scheduler: project.github_assignee not set, skipping.")
        return

    required_label = CONFIG["project"].get("differentiating_label")
    issues = github_client.get_assigned_issues(assignee, required_label=required_label)
    logger.info(
        "Scheduler: fetched %d issue(s) for assignee=%s label=%s",
        len(issues), assignee, required_label or "(none)",
    )
    if not issues:
        logger.info("Scheduler: no assigned issues found.")
        return

    issue = issues[0]
    logger.info("Scheduler: starting task from issue #%d: %s", issue.number, issue.title)
    task_desc = f"#{issue.number}: {issue.title}\n\n{issue.body}"
    session.reset()
    import asyncio as _asyncio
    _asyncio.create_task(run_workflow_async(task_desc, issue_number=issue.number))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cli_run() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py '<task description>'")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    print(f"AutoDev CLI — task: {task}\n")
    workflow_config = WorkflowConfig(
        max_self_correction_attempts=CONFIG["agent"]["max_self_correction_attempts"],
        max_steps_per_session=CONFIG["agent"]["max_steps_per_session"],
        run_tests=CONFIG["project"].get("run_tests", True),
    )
    workflow = Workflow(session=session, planner=planner, engine=engine, config=workflow_config)
    workflow.run(task)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        cli_run()
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
