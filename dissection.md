# AutoDev — Codebase Dissection

A guide to understanding how everything fits together. Start here before diving into any file.

---

## The Big Picture

AutoDev is a loop:

```
GitHub Issue (or manual task)
  → AI generates a plan
  → You review & approve the plan
  → AI implements step by step (runs tests, fixes its own mistakes)
  → You review the final diff
  → AutoDev pushes a branch and opens a PR
```

Everything in the codebase exists to support one of these steps. The key design choice is that **you are always in control** — the AI never pushes code without your explicit approval.

---

## File Map

```
backend/
├── main.py                  ← Entry point. Wires everything together.
├── config.yaml              ← All user-facing settings (schedule, providers, repo).
│
├── api/
│   ├── routes.py            ← Every HTTP endpoint the frontend calls.
│   ├── auth.py              ← Bearer token check on every request.
│   └── sse.py               ← Live log streaming (Server-Sent Events).
│
├── orchestrator/
│   ├── workflow.py          ← The core state machine (plan → code → review).
│   ├── planner.py           ← Asks the LLM to generate/refine a plan.
│   ├── context_loader.py    ← Reads the target repo to give the LLM context.
│   └── session.py           ← Saves task state to disk (survives restarts).
│
├── engine/
│   ├── base.py              ← Abstract interface: what every coding engine must do.
│   ├── aider_engine.py      ← Aider implementation of that interface.
│   └── result.py            ← EngineResult and TestResult dataclasses.
│
├── integrations/
│   ├── llm_client.py        ← LiteLLM wrapper: rate limiting, fallbacks, token tracking.
│   ├── usage_db.py          ← SQLite: daily token budgets per provider.
│   ├── github_client.py     ← PyGitHub: fetch issues, open PRs.
│   └── git_client.py        ← GitPython: clone, branch, push, safety checks.
│
└── prompts/
    ├── planning.txt         ← Prompt template: "generate a plan for this task"
    ├── refinement.txt       ← Prompt template: "refine the plan given this feedback"
    └── self_review.txt      ← Prompt template: "review your own diff"

frontend/src/
├── routes/
│   ├── +page.svelte         ← Dashboard: agent status, issues, token usage.
│   ├── plan/[id]/           ← Plan review: see the plan, add comments, approve.
│   ├── log/[id]/            ← Live log: SSE stream + step-failure controls.
│   ├── diff/[id]/           ← Final diff: syntax-highlighted, approve/reject.
│   ├── history/             ← Past tasks (read-only).
│   └── logs/                ← Agent log file viewer (/data/autodev.log).
└── lib/
    ├── api.ts               ← All fetch calls to the FastAPI backend.
    ├── LogStream.svelte      ← SSE consumer: displays live log lines.
    └── DiffViewer.svelte     ← Renders a unified diff with syntax highlighting.
```

---

## How a Task Flows Through the Code

### 1. Task is created

`POST /tasks` → `routes.py:create_task` → calls `run_workflow_async(task)` as an asyncio background task.

`run_workflow_async` is defined in `main.py`. It:
- Clones the target repo into `/tmp/autodev-task-{id}/` (`git_client.clone_ephemeral`)
- Runs a git safety check (dirty tree / merge conflict → halt)
- Creates a feature branch (`autodev/issue-42` or `autodev/task-{id[:8]}`)
- Builds **callback functions** that block until the API signals them
- Runs `Workflow.run(task)` in a thread pool (since Aider is synchronous)

### 2. Planning

`workflow.py:Workflow.run` calls `planner.generate_plan(task)`.

`planner.py` calls the LLM through `llm_client.py`. The prompt is loaded from `prompts/planning.txt`. The plan comes back as a list of strings — one item per implementation step.

Session state is updated to `awaiting_plan_review` and the plan is saved.

### 3. Plan review (human in the loop)

The workflow calls `_review_plan_cb()`, which **blocks** on `threading.Event.wait()`.

The frontend polls `GET /tasks/{id}` and sees `awaiting_plan_review`. The user either:
- Approves → `POST /tasks/{id}/plan/approve` → sets `plan_action="approve"` and fires the event
- Comments → `POST /tasks/{id}/plan/comment` → sets `plan_action="refine"`, stores comment, fires the event

When the event fires, the callback returns `(True, None)` or `(False, comment)` to the workflow. If refine, the workflow calls `planner.refine_plan(plan, comment)` and loops back.

### 4. Implementation

For each step in the plan, `workflow.py:_run_step_with_correction` is called.

This calls `engine.execute_task(step, files=[])`. The engine is `AiderEngine` (`engine/aider_engine.py`), which creates an Aider `Coder` instance pointing at the cloned repo and runs the step description as a prompt.

After Aider edits files, if `run_tests=True`:
- `engine.run_tests()` runs the linter then the test suite as subprocesses
- If they fail, `engine.inject_comment(correction_prompt)` is called — Aider tries to fix its own errors
- This self-correction repeats up to `max_self_correction_attempts` (config)
- If the cap is hit, the workflow sets status to `awaiting_step_review` and blocks on another threading.Event, waiting for the user to abort/skip/retry

### 5. Diff review

After all steps, `engine.get_diff()` gets the full unified diff (via `git diff HEAD` in the cloned repo). Status becomes `awaiting_diff_review`.

User sees the diff in `diff/[id]/+page.svelte`. They approve or reject:
- Approve → workflow pushes the branch, opens a PR, wipes the temp dir
- Reject → temp dir is wiped, status goes back to idle

### 6. Push and PR

`git_client.push_branch(repo, branch_name)` pushes to origin.
`github_client.open_pull_request(branch, title, body, base)` opens the PR via GitHub API.

---

## Key Design Decisions

### Threading vs async

The workflow (`workflow.py`) runs in `asyncio.get_event_loop().run_in_executor()` — a thread pool. This is because Aider is synchronous (blocking) and can't be awaited. FastAPI is async (non-blocking).

The bridge between them is `threading.Event` — not `asyncio.Event`. The workflow thread calls `.wait()` to block. The API route handlers call `.set()` to unblock. This is the only correct way when one side is sync and the other is async.

### CodingEngine interface

`engine/base.py` defines the `CodingEngine` abstract base class with 5 methods: `execute_task`, `get_diff`, `run_tests`, `inject_comment`, `reset`. Nothing outside `engine/` imports Aider directly. This means Aider can be swapped out in Phase 10 by writing a new class — no other code changes needed.

### Ephemeral repos

Every task gets a fresh clone in `/tmp/autodev-task-{id}/`. This directory is wiped when the task completes (approved or rejected). The Docker volume at `/data/` only holds `session.json`, `usage.db`, and `autodev.log` — never the working code.

### Session state

`session.py` persists state to `/data/session.json`. This means if the container restarts mid-task, the state is preserved. The agent can pick up where it left off (the next scheduled run checks the persisted status).

### Token budgets

`usage_db.py` tracks token usage in SQLite. Every LLM call goes through `llm_client.py`, which checks the daily budget before calling and updates it after. If a provider is exhausted, the fallback chain tries the next one. If all are exhausted, the workflow halts with `halted:credits_exhausted`.

---

## app_state — The Glue

`main.py` keeps a global `app_state` dictionary:

```python
app_state = {
    "session": session,          # SessionManager instance
    "usage_db": usage_db,        # UsageDB instance
    "engine": engine,            # AiderEngine instance
    "planner": planner,          # Planner instance
    "github_client": github_client,  # GitHubClient or None
    "git_client": git_client,    # GitClient instance
    # Per-task signalling events (reset for each new task):
    "plan_event": threading.Event(),
    "plan_action": None,
    "plan_comment": "",
    "diff_event": threading.Event(),
    "diff_action": None,
    "step_failure_event": threading.Event(),
    "step_failure_choice": "abort",
}
```

Routes import `app_state` from `main` (`from main import app_state`) to read session state and fire events. This is intentionally simple — no dependency injection framework, just a module-level dict.

---

## SSE (Live Logs)

`api/sse.py` maintains a dict mapping `task_id → asyncio.Queue`. The workflow's `_log()` function calls `publish_log(task_id, message)` which puts a message on the queue.

The `GET /tasks/{id}/stream` endpoint reads from the queue and streams each message as an SSE event. The frontend's `LogStream.svelte` component opens an `EventSource` connection and appends each message to the log display.

Because `EventSource` can't send custom headers, the token is passed as `?token=` in the URL. `auth.py` accepts both the `Authorization: Bearer` header and the `?token=` query param.

---

## Config Hierarchy

```
config.yaml          ← everything user-configurable
backend/.env         ← secrets (API keys, tokens) — never commit
Docker environment   ← AUTODEV_DATA_DIR override for /data path
```

`main.py` loads `config.yaml` at startup into `CONFIG` (module-level dict). All other modules that need config receive it as constructor arguments — they never read from disk themselves.

---

## Where to Look for Common Tasks

| I want to…                              | Look at…                          |
|-----------------------------------------|-----------------------------------|
| Change how the plan is generated        | `prompts/planning.txt`, `orchestrator/planner.py` |
| Change how the agent implements code    | `engine/aider_engine.py`          |
| Add a new API endpoint                  | `api/routes.py`                   |
| Add a new UI page                       | `frontend/src/routes/`            |
| Change rate limiting / fallback logic   | `integrations/llm_client.py`      |
| Change what gets saved between restarts | `orchestrator/session.py`         |
| Change the schedule                     | `config.yaml` → `schedule.time`  |
| Swap Aider for something else           | Write a new class in `engine/`, set `engine.provider` in `config.yaml` |

---

## Running Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

Tests mock the LLM, engine, and GitHub/git clients so they run without any API keys.
