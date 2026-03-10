# AutoDev — Refined Project Plan
*An automated, human-in-the-loop AI coding agent*

---

## Vision

A scheduled program that uses your free daily AI credits to make incremental, reviewed progress on a project of your choice. You stay in control at every key decision point — the AI does the work, you steer the direction and approve the results.

Longer term, AutoDev registers as a robot in RoboMesh, your robot management system. RoboMesh becomes the single dashboard for everything you're running — physical robots and your coding agent alike.

---

## Long-Term Integration Picture

```
RoboMesh (Go + Svelte)
├── roboserver              ← central hub, orchestrates all robots
│   ├── physical robots     ← existing C/C++ robot clients
│   └── AutoDev agent       ← NEW: just another robot in the mesh
│       └── dispatches tasks, monitors status, surfaces results
│
└── frontend_app (Svelte)
    └── unified dashboard: robots + AutoDev in one place

AutoDev (Python + FastAPI + Svelte)
├── Standalone today        ← its own Svelte UI for review workflow
└── RoboMesh client later   ← roboserver calls AutoDev's API directly
    └── AutoDev exposes the same clean REST API either way
```

The key design principle: build AutoDev's API surface as if RoboMesh will be its client someday, not just your browser. That makes the future integration essentially free — RoboMesh just starts calling the endpoints instead of you doing it through a browser.

RoboMesh can be found here: https://github.com/shaply/Robomesh.

---

## Core Architecture

```
┌────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                        │
│                (Python — while loop → LangGraph)           │
│                                                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │  Scheduler  │  │  GitHub      │  │  FastAPI           │ │
│  │ APScheduler │  │  PyGitHub    │  │  REST + SSE        │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Credit/Quota Router (LiteLLM)           │  │
│  │   Claude API → Gemini → Groq → fallback chain        │  │
│  │   Usage persisted to SQLite (timezone-aware)         │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CODING ENGINE INTERFACE                  │
│                  (Abstract Base Class)                      │
│                                                             │
│   execute_task(task, files) → EngineResult                  │
│   get_diff() → str                                          │
│   run_tests() → TestResult                                  │
│   inject_comment(comment) → None                            │
│   reset() → None                                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    AIDER ENGINE (v1)                        │
│              Implements CodingEngine ABC                    │
│  • Context window management (handled by Aider)             │
│  • File editing and diffs (handled by Aider)                │
│  • Works on ephemeral repo clone per task                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow

```
START (scheduled or manual trigger)
         │
         ▼
┌─────────────────────┐
│   Git safety check  │  ← dirty tree or merge conflict?
│   Halt + alert if   │    → STOP, notify user, do not proceed
│   repo is unclean   │
└──────────┬──────────┘
           │ CLEAN
           ▼
┌─────────────────────┐
│   Fresh ephemeral   │  ← clone repo into temp dir inside container
│   repo clone        │    mounted volume only holds logs + state
└──────────┬──────────┘
           │
    ┌──────▼──────┐
    │  GitHub     │
    │  issues     │
    │  assigned?  │
    └──┬──────┬───┘
      YES     NO
       │       │
       │       ▼
       │  Ask user for
       │  task / direction
       │  (via Svelte UI)
       │       │
       └───────┴────┐
                    ▼
        ┌───────────────────┐
        │  PLANNING PHASE   │
        │  AI generates     │
        │  step-by-step     │
        │  attack plan      │
        └─────────┬─────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  HUMAN REVIEW 1   │◄──── add comments (Svelte UI)
        │  Review plan      │      AI refines
        │  Approve/reject   │      loop until approved
        └─────────┬─────────┘
                  │ APPROVED
                  ▼
        ┌───────────────────┐
        │  IMPLEMENTATION   │◄──── inject comments anytime
        │  LOOP (per step)  │      live log stream via SSE
        │  • Edit files     │
        │  • Run linter     │  ← from Phase 2 onward
        │  • Run tests      │  ← self-correction loop
        │  • AI self-review │
        │  • Repeat steps   │
        └─────────┬─────────┘
                  │ TASK COMPLETE or CREDITS EXHAUSTED
                  ▼
        ┌───────────────────┐
        │  HUMAN REVIEW 2   │◄──── final diff review (Svelte UI)
        │  Approve → push   │      or merge the PR on GitHub
        │  Reject → discard │
        │  & wipe temp dir  │
        └─────────┬─────────┘
                  │ APPROVED
                  ▼
        Push branch / open PR on GitHub
        Wipe ephemeral temp dir
                  │
                  ▼
              LOOP BACK
```

---

## Project Structure

```
autodev/
├── docker-compose.yml                 # Mini PC deployment
├── Dockerfile                         # Agent container
│
├── backend/                           # Python + FastAPI
│   ├── main.py                        # FastAPI app + APScheduler entry point
│   ├── config.yaml                    # User config (project, schedule, providers)
│   ├── .env.example                   # Committed placeholder (never commit real .env)
│   ├── requirements.txt
│   │
│   ├── api/
│   │   ├── routes.py                  # REST endpoints
│   │   ├── auth.py                    # Bearer token middleware
│   │   └── sse.py                     # Server-Sent Events log stream
│   │
│   ├── orchestrator/
│   │   ├── workflow.py                # State machine: while loop (Ph1-2) → LangGraph (Ph3+)
│   │   ├── planner.py                 # Generate + refine implementation plan
│   │   ├── context_loader.py          # Load project, build file tree summary
│   │   └── session.py                 # Persist session state to disk (JSON)
│   │
│   ├── engine/
│   │   ├── base.py                    # CodingEngine abstract base class ⭐
│   │   ├── aider_engine.py            # Aider implementation of CodingEngine
│   │   └── result.py                  # EngineResult, TestResult dataclasses
│   │
│   ├── integrations/
│   │   ├── llm_client.py              # LiteLLM wrapper + quota/fallback logic
│   │   ├── usage_db.py                # SQLite token budget tracking (timezone-aware)
│   │   ├── github_client.py           # GitHub API (issues, PRs, commits)
│   │   └── git_client.py              # Local git ops + safety checks (GitPython)
│   │
│   └── prompts/
│       ├── planning.txt               # Planning phase prompt templates
│       ├── refinement.txt             # Plan refinement after user feedback
│       └── self_review.txt            # AI self-review of its own diff
│
└── frontend/                          # Svelte + TypeScript
    ├── src/
    │   ├── routes/
    │   │   ├── +page.svelte           # Dashboard / current task status
    │   │   ├── plan/+page.svelte      # Plan review + comment UI
    │   │   ├── diff/+page.svelte      # Final diff review + approve/reject
    │   │   └── history/+page.svelte   # Past task history
    │   │
    │   └── lib/
    │       ├── LogStream.svelte       # SSE live log viewer
    │       ├── DiffViewer.svelte      # Syntax-highlighted diff display
    │       └── api.ts                 # Typed API client for FastAPI
    │
    └── package.json
```

---

## API Surface (FastAPI)

Designed to be called by your Svelte UI today, and by RoboMesh's `roboserver` in the future. The contract doesn't change — only who's calling it does.

```
POST   /tasks                   → create a new task (manual or from issue)
GET    /tasks                   → list all tasks (history)
GET    /tasks/{id}              → get task detail + current state
GET    /tasks/{id}/plan         → fetch the current plan
POST   /tasks/{id}/plan/comment → add a comment to the plan
POST   /tasks/{id}/plan/approve → approve plan, start implementation
POST   /tasks/{id}/comment      → inject comment during implementation
GET    /tasks/{id}/diff         → get current unified diff
POST   /tasks/{id}/diff/approve → approve final diff, push branch + open PR
POST   /tasks/{id}/diff/reject  → discard all changes, wipe temp dir

GET    /status                  → agent status (idle/planning/coding/awaiting_review/halted)
GET    /usage                   → daily token usage per provider (from SQLite)

GET    /tasks/{id}/stream       → SSE: live log output during implementation
```

Note: `/status` now includes a `halted` state for when the agent stops due to a dirty git tree, merge conflict, or provider exhaustion.

### Authentication

Every endpoint must require a bearer token. The agent holds GitHub credentials and can push code — this is not optional even on a private network.

```python
# backend/.env
AUTODEV_API_TOKEN=your-random-secret-here

# FastAPI middleware: check Authorization: Bearer <token> on every request
# Return 401 if missing or wrong — no exceptions
```

The Svelte frontend reads `VITE_API_TOKEN` from its own `.env` and injects it into every request header via `api.ts`. Both `.env` files must be in `.gitignore` and a `.env.example` with placeholder values should be committed instead.

---

## The `CodingEngine` Interface (Key Design Decision)

This is the most important architectural decision in the whole project. By hiding Aider behind an abstract interface, you can swap it out in the future without touching any other part of the system.

```python
# engine/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class EngineResult:
    success: bool
    diff: str
    files_changed: list[str]
    error: str | None = None

@dataclass
class TestResult:
    passed: bool
    output: str

class CodingEngine(ABC):

    @abstractmethod
    def execute_task(self, task: str, files: list[str]) -> EngineResult:
        """Given a task description and relevant files, implement the changes."""
        pass

    @abstractmethod
    def get_diff(self) -> str:
        """Return a unified diff of all changes made so far."""
        pass

    @abstractmethod
    def run_tests(self) -> TestResult:
        """Run the project's test suite and return results."""
        pass

    @abstractmethod
    def inject_comment(self, comment: str) -> None:
        """Accept a mid-implementation comment from the user and adjust course."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Discard all changes (user rejected the final review)."""
        pass
```

```python
# engine/aider_engine.py
from .base import CodingEngine, EngineResult, TestResult
from aider.coders import Coder
from aider.models import Model

class AiderEngine(CodingEngine):

    def __init__(self, model_name: str, repo_path: str):
        self.model = Model(model_name)
        self.repo_path = repo_path  # ephemeral temp dir clone
        self.coder = None           # initialized per task

    def execute_task(self, task: str, files: list[str]) -> EngineResult:
        self.coder = Coder.create(
            main_model=self.model,
            fnames=files,
            auto_commits=False      # we control commits
        )
        self.coder.run(task)
        return EngineResult(
            success=True,
            diff=self.get_diff(),
            files_changed=files
        )

    def get_diff(self) -> str:
        # use GitPython to get diff against HEAD
        ...

    def run_tests(self) -> TestResult:
        # run pytest / npm test / etc. as subprocess inside temp dir
        ...

    def inject_comment(self, comment: str) -> None:
        if self.coder:
            self.coder.run(comment)

    def reset(self) -> None:
        # wipe the ephemeral temp dir entirely
        ...
```

When you eventually want to swap Aider out, you write a new class that inherits from `CodingEngine` and implement the same 5 methods. The orchestrator never knows the difference.

---

## Tech Stack

| Component | Tool | Why |
|---|---|---|
| Agent language | Python 3.11+ | Best AI/LLM ecosystem, required for Aider |
| Agent framework | while loop → LangGraph | Simple loop in Ph1-2; LangGraph added in Ph3 when async state management is actually needed |
| LLM routing | LiteLLM | Single API for Claude, Gemini, Groq. Built-in quota tracking |
| Coding engine | Aider (via Python API) | Handles context window, file editing, diffs — battle-tested |
| Backend API | FastAPI | Lightweight, async-native, clean SSE support |
| Live streaming | Server-Sent Events (SSE) | Simpler than WebSockets for unidirectional server→client log streaming |
| Frontend | Svelte + TypeScript | Consistent with RoboMesh; reactive, integrates naturally with SSE |
| GitHub integration | PyGitHub + GitPython | Issues, PRs, local git ops + safety checks |
| Scheduling | APScheduler | Pure Python, no system cron needed |
| Session state | JSON file | Simple, no database needed for workflow state |
| Token budgets | SQLite (`usage_db.py`) | Survives restarts; atomic writes; timezone-aware daily resets |
| Deployment | Docker + docker-compose | Dependency isolation on mini PC; ephemeral repo clones |
| Remote access | Tailscale | Access UI from anywhere, zero config, no open ports |
| Testing | pytest / linter | Run after every implementation step from Phase 2 onward |

---

## Deployment

AutoDev runs on your mini PC as a persistent Docker container. The mounted volume only holds session state, logs, and the SQLite usage database — never the live working repo. Each task gets a fresh ephemeral clone inside the container that is wiped after approval or rejection.

```
Mini PC (always on)
├── Docker: autodev-backend  (Python + FastAPI, port 8000)
└── Docker: autodev-frontend (Svelte, port 5173)
    │
    ├── Agent runs on schedule (APScheduler inside backend)
    ├── Git safety check before every run — halts on dirty tree / conflict
    ├── Clones repo into ephemeral /tmp/task-{id}/ inside container
    ├── Works on a feature branch in that temp dir
    ├── On approval: pushes branch, opens PR on GitHub, wipes temp dir
    └── FastAPI serves REST + SSE for the Svelte UI

Your laptop / phone
├── http://mini-pc-ip:5173        ← on home network
└── http://mini-pc.tailnet:5173   ← anywhere via Tailscale
    ├── Review the plan, add comments
    ├── Watch live implementation log (SSE stream)
    ├── Approve/reject final diff
    └── Final merge happens on GitHub.com
```

**docker-compose.yml** (sketch):
```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data          # session state, SQLite usage DB, logs only
                              # NOT the working repo — that stays ephemeral
    env_file: .env            # API keys

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://backend:8000
    depends_on:
      - backend
```

---

## Token Budget Tracking (`usage_db.py`)

Token usage must survive container restarts and reset correctly at midnight in the configured timezone. JSON session state is not reliable enough for this — a mid-task restart could cause the agent to lose its tally and blow past free tier limits.

```python
# integrations/usage_db.py
# SQLite schema: (provider TEXT, date TEXT, tokens_used INTEGER)
# date is always stored as YYYY-MM-DD in the configured local timezone
# reset = simply no row exists for today's date yet
# query = SELECT tokens_used WHERE provider=? AND date=today_local()
```

Key rules:
- Always derive "today" from the configured timezone in `config.yaml`, not UTC
- On agent startup, read today's usage from SQLite before routing any requests
- After every LiteLLM call, immediately write the updated count back to SQLite
- The fallback chain triggers when `tokens_used >= daily_token_budget` for a provider

---

## Git Safety Protocol (`git_client.py`)

Before every scheduled run, the agent checks the state of the repo. It never attempts to resolve conflicts autonomously.

```
On startup:
  1. Check for uncommitted changes → HALT if dirty
  2. Check for unresolved merge conflicts → HALT if any
  3. Pull latest from remote → HALT if pull fails
  4. Create feature branch from clean HEAD → proceed

On HALT:
  → Set agent status to "halted"
  → Surface clear error message in UI ("Merge conflict detected in main —
     resolve manually before AutoDev can proceed")
  → Send notification (future: email / push)
  → Exit without touching any files
```

---

## Concurrency & Task Queuing

The agent is single-threaded by design — it runs one task at a time. This creates two conflict scenarios that need explicit defined behavior:

**Scheduler fires while a task is in progress:**
```
If agent state is anything other than "idle" at scheduled run time:
  → Skip this scheduled run entirely
  → Log: "Scheduled run skipped — task {id} already in progress"
  → Do NOT queue, do NOT interrupt
```

**Manual task created via POST /tasks while agent is busy:**
```
If agent state is not "idle":
  → Return HTTP 409 Conflict
  → Body: { "error": "Agent busy", "current_task": "{id}", "state": "{state}" }
  → Client (UI or RoboMesh) is responsible for retrying or notifying user
```

This keeps the agent simple and predictable. A task queue can be added later if needed, but "one task at a time, loudly reject conflicts" is the right v1 behavior.

---

## Partial Work on Credit Exhaustion

When all providers are exhausted mid-task, the agent halts with partial work done. The behavior must be defined explicitly:

```
On credit exhaustion mid-implementation:
  1. Finish the current step cleanly (do not interrupt mid-edit)
  2. Save session state: { task_id, plan, last_completed_step, partial_diff }
  3. Set status to "halted:credits_exhausted"
  4. The partial diff IS accessible via GET /tasks/{id}/diff
  5. Surface in UI: "Credits exhausted after step 3 of 7 — review partial work
     or wait until tomorrow to continue"

User options from the UI:
  → "Review partial diff" — see what was done, approve to push as-is, reject to discard
  → "Resume tomorrow" — session state preserved, next scheduled run picks up at step 4
  → "Discard" — wipe temp dir, mark task abandoned

On next scheduled run, if state is "halted:credits_exhausted":
  → Check if user chose "Resume" — if yes, continue from last_completed_step
  → Do not start a new task automatically
```

This also needs a config value for the self-correction loop cap:

```yaml
# config.yaml addition
agent:
  max_self_correction_attempts: 3   # per step, before surfacing failure to user
  max_steps_per_session: 20         # safety cap on total plan steps
```

If the self-correction cap is hit, the agent surfaces the failure to you rather than continuing to consume credits on a problem it can't solve. You then decide: inject a comment with a new approach, skip the step, or abort.

Free tiers impose several distinct types of limits, all of which need to be handled independently. Conflating them is a common mistake that leads to either wasted credits or silent failures.

### The Four Limit Types

| Limit | What it is | Consequence if ignored |
|---|---|---|
| **Daily token budget** | Max tokens per calendar day | Agent blows past free tier, incurs charges |
| **RPM** (requests per minute) | Max API calls per 60s window | 429 error mid-implementation step, task crash |
| **TPM** (tokens per minute) | Max tokens processed per 60s | 429 even with daily budget remaining |
| **Context window** | Max tokens in a single request | Hard failure if a file or diff is too large |

### Free Tier Reference (as of 2025 — verify before building)

| Provider | RPM | TPM | Daily limit | Context window |
|---|---|---|---|---|
| Claude (Anthropic free) | 5 | 25,000 | 25,000 tokens | 200k |
| Gemini 1.5 Flash (free) | 15 | 1,000,000 | 1,500 requests | 1M |
| Groq (Llama 3.1 70B free) | 30 | 6,000 | ~100k tokens | 128k |

> **Always re-check these before starting Phase 6.** Free tier limits change frequently and without notice. The RPM limits in particular are the most likely to bite you — Aider can make 3–6 API calls per implementation step, so a 5 RPM limit means you're rate-limited after a single step on Claude's free tier.

### Retry & Backoff Protocol

Every API call in `llm_client.py` must handle 429 responses without crashing. The correct pattern is exponential backoff with jitter:

```python
# integrations/llm_client.py
import time, random

def call_with_backoff(fn, max_retries=5):
    for attempt in range(max_retries):
        try:
            return fn()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise  # exhausted retries → trigger provider fallback
            wait = (2 ** attempt) + random.uniform(0, 1)  # jitter
            log(f"Rate limited. Waiting {wait:.1f}s before retry {attempt+1}...")
            time.sleep(wait)
```

Key rules:
- On a 429: wait and retry with the current provider first (up to `max_retries`)
- If retries are exhausted: treat it the same as a daily budget exhaustion → trigger fallback to next provider
- Respect `Retry-After` headers if the provider sends them — use that value instead of the backoff calculation
- Never retry immediately — even a 1-second wait is meaningless; start at 2 seconds minimum

### RPM Throttling

For providers with very low RPM limits (Claude free tier at 5 RPM), add a minimum inter-request delay in `llm_client.py` to avoid hitting the limit in the first place rather than relying purely on retry logic:

```python
# Enforce minimum gap between requests to stay under RPM limit
MIN_REQUEST_INTERVAL = {
    "claude": 12.0,   # 5 RPM → 1 request per 12s to be safe
    "gemini": 4.0,    # 15 RPM → 1 request per 4s
    "groq":   2.0,    # 30 RPM → 1 request per 2s
}
```

This is proactive throttling — the agent paces itself rather than firing requests and absorbing 429s.

### Context Window Failures

Context window exceeded is a hard failure — no retry will fix it. The response is to truncate or summarize the input:

```
On context window error:
  1. Log which file/prompt caused the overflow
  2. Attempt to truncate: send only the diff, not full file contents
  3. If still too large: skip the step, log a warning, continue to next step
  4. Surface truncation warnings in the UI so you're aware
  5. Never silently drop content without noting it in the session log
```

This is also the earliest indicator that you need the context intelligence upgrade in Phase 9.

### SQLite Schema Update

Add RPM/TPM tracking columns to `usage_db.py` to enable the proactive throttling logic:

```python
# Extended schema:
# (provider TEXT, date TEXT, tokens_used INTEGER,
#  requests_this_minute INTEGER, last_request_ts REAL)
# last_request_ts: Unix timestamp of most recent call
# requests_this_minute: rolling count, reset when current_ts - last_request_ts > 60
```

---

## Implementation Phases

---

### PHASE 1 — Foundation
*Goal: the bare minimum working loop, local CLI only, simple while loop*

- [x] Python project setup, `config.yaml` schema (including RPM limits per provider)
- [x] LiteLLM client wrapper with basic Claude + Gemini support
- [x] **Exponential backoff + jitter on every API call from day one** — 429 handling is not optional even in Phase 1
- [x] **Proactive RPM throttling**: minimum inter-request delay per provider in `llm_client.py`
- [x] `context_loader.py`: read a local directory, generate a file tree + README summary
- [x] `CodingEngine` ABC + `AiderEngine`: wrap Aider's Python API behind the interface
- [x] Simple CLI: accept a task string, pass to Aider, show diff in terminal
- [x] Basic session state saved to JSON (current task, status)
- [x] Workflow: plain `while` loop over a state dict — no LangGraph yet

**Exit criteria:** You can type a task, the agent edits files, you see a diff, you approve/reject. A 429 response causes a logged wait-and-retry, not a crash. A second `POST /tasks` while one is running returns a 409.

---

### PHASE 2 — Planning Loop + Early Test Execution
*Goal: the AI plans before it codes, tests run automatically after every step*

- [ ] `planner.py`: generate a structured plan (numbered steps, files to touch, risks)
- [ ] Plan review in CLI: display plan, accept free-text comments
- [ ] Refinement loop: re-prompt AI with your comments, repeat until approved
- [ ] Approval gate: implementation does not start until user types "approve"
- [ ] **Linter + test runner after every implementation step** — agent self-corrects on failure before surfacing to you
- [ ] **`max_self_correction_attempts` cap** — after N failed attempts per step, surface failure to user instead of burning more credits
- [ ] Session state now tracks: current plan, step index, comment history, test results per step

**Exit criteria:** Full plan → review → refine → approve → code → per-step tests → diff loop works end-to-end. Agent catches its own syntax errors without human review.

---

### PHASE 3 — Docker + FastAPI Backend + LangGraph
*Goal: move off CLI, get the agent running as a proper service; introduce LangGraph now that async state management is needed*

- [ ] **Bearer token auth middleware** (`auth.py`): every endpoint requires `Authorization: Bearer <token>`, returns 401 otherwise
- [ ] **Concurrency enforcement**: `POST /tasks` returns 409 if agent is not idle; scheduler skips if agent is busy
- [ ] Dockerfile for the backend, `docker-compose.yml` for the full stack
- [ ] Ephemeral repo clone per task: agent works in `/tmp/task-{id}/`, volume only holds state + logs
- [ ] Git safety check on every startup: dirty tree / merge conflict → halt + alert
- [ ] FastAPI app wrapping the orchestrator: all workflow transitions via API endpoints
- [ ] **Replace while loop with LangGraph** — now that FastAPI needs to manage long-running async state across HTTP requests, LangGraph earns its place
- [ ] **SSE endpoint** (`GET /tasks/{id}/stream`) streaming live agent log output — not WebSockets
- [ ] Tailscale installed on mini PC, backend accessible remotely

**Exit criteria:** Agent runs in Docker on mini PC. You can hit the API from your laptop and see live logs via SSE. Git safety checks prevent the agent from running on a dirty repo.

---

### PHASE 4 — Svelte Frontend
*Goal: browser-based review UI replacing the CLI*

- [ ] Svelte + TypeScript project setup, typed API client (`api.ts`)
- [ ] Dashboard page: current task status, agent state (including `halted`), token usage
- [ ] **Partial work UI**: when state is `halted:credits_exhausted`, show options — review partial diff, resume tomorrow, or discard
- [ ] **Self-correction failure UI**: when step hits `max_self_correction_attempts`, surface the failure with options to inject a new approach, skip the step, or abort
- [ ] Plan review page: formatted plan, comment box, approve/reject buttons
- [ ] Live log page: `LogStream.svelte` consuming SSE stream, real-time output
- [ ] Diff viewer page: `DiffViewer.svelte` with syntax highlighting, approve/reject
- [ ] Task history page: past tasks, their plans, per-step test results, outcomes
- [ ] Halt alert: prominent UI state when agent is blocked on git conflict

**Exit criteria:** Full plan → review → approve → watch implementation → final diff → approve, all from the browser. CLI no longer needed.

---

### PHASE 5 — GitHub Integration
*Goal: connect to a real project with issues and PRs*

- [ ] `github_client.py`: authenticate, list issues assigned to you, fetch issue body + comments
- [ ] Issue-as-task: surface assigned issues in the UI as selectable task options
- [ ] Commit changes to a new branch named after the task (`feature/issue-42-...`)
- [ ] Open a PR with auto-generated description summarizing what was done and which files changed
- [ ] Support both local-only mode (no GitHub) and remote mode (config toggle)

**Exit criteria:** Agent reads a GitHub issue, codes a fix, opens a PR. You merge it on GitHub.

---

### PHASE 6 — Scheduler + Multi-Provider Credit Routing
*Goal: runs automatically every day, burns the right provider's free credits, survives restarts*

- [ ] APScheduler integration: run at configured time daily (or on demand via API)
- [ ] `usage_db.py`: SQLite token budget tracking — survives restarts, resets by calendar date in configured timezone
- [ ] Provider quota config: specify daily token budgets per provider
- [ ] Fallback chain: if Claude quota hit → switch to Gemini → switch to Groq
- [ ] Graceful stop: if all providers exhausted mid-task, save state and halt cleanly (resume tomorrow)
- [ ] Usage chart in Svelte dashboard: daily tokens per provider

**Exit criteria:** Agent runs unattended at midnight, uses free Claude credits first, falls back to Gemini, stops cleanly when all daily quotas hit. Token counts survive a container restart. Usage chart visible in UI.

---

### PHASE 7 — Implementation Controls
*Goal: more granular mid-task control*

- [ ] Mid-implementation comment injection via UI (calls `engine.inject_comment()`)
- [ ] Step-by-step mode: optionally pause between each plan step for micro-review in browser
- [ ] AI self-review: after each step, AI reviews its own diff and flags issues before showing you

**Exit criteria:** You can interrupt the agent mid-task from the browser and redirect it.

---

### PHASE 8 — RoboMesh Integration
*Goal: AutoDev becomes a robot managed by RoboMesh*

This phase requires RoboMesh to be sufficiently developed to support external robot clients with a defined protocol.

- [ ] Understand RoboMesh's robot registration + communication protocol (`roboserver` API)
- [ ] Implement a RoboMesh client adapter: registers on startup, sends heartbeats, receives task commands
- [ ] Map RoboMesh task dispatch → AutoDev `POST /tasks`
- [ ] Map AutoDev status → RoboMesh robot status format
- [ ] AutoDev's existing Svelte UI remains available as a drill-down from RoboMesh's dashboard

**Exit criteria:** AutoDev appears in RoboMesh's robot list. You can dispatch a coding task from RoboMesh and watch it execute.

---

### PHASE 9 — Context Intelligence Upgrade
*Goal: handle large codebases without hitting token limits*

- [ ] Study SWE-agent's Agent-Computer Interface (ACI) pattern — understand before building
- [ ] Implement tool-based context: give AI structured tools (`read_file`, `search_codebase`, `list_functions`) instead of dumping files
- [ ] Running session summary: compact "what we've done this session" block prepended to every prompt
- [ ] Optionally: integrate LlamaIndex or ChromaDB for RAG on very large repos (100k+ lines)

**Exit criteria:** Agent can navigate a large monorepo and only pull in relevant files per task.

---

### PHASE 10 — Custom Coding Engine
*Goal: replace Aider with your own implementation when needed*

This phase only becomes relevant if Aider is deprecated, under-performing, or you want capabilities it doesn't support. Because you built behind `CodingEngine` from day one, this is just writing a new class.

- [ ] Research SWE-agent's file editing approach and ACI as implementation reference
- [ ] Design `MyEngine` implementing `CodingEngine`
- [ ] Implement: file reading, targeted editing (tree-sitter for AST-aware edits), diff generation, test running
- [ ] Benchmark against Aider on a set of your own historical tasks
- [ ] Swap in via config: `engine: my_engine` → done, zero other changes

**Exit criteria:** You can switch engines in `config.yaml` with no other code changes.

---

## Configuration File (`config.yaml`)

```yaml
agent:
  max_self_correction_attempts: 3   # per step, before surfacing failure to user
  max_steps_per_session: 20         # safety cap on total plan steps executed per run

project:
  github_repo: user/my-app         # repo to clone per task
  test_command: pytest              # command to run after every implementation step
  lint_command: ruff check .        # linter to run before tests

schedule:
  enabled: true
  time: "23:30"                     # run daily at 11:30 PM
  timezone: "America/New_York"      # used for SQLite daily budget resets

engine:
  provider: aider                   # swap to "my_engine" in Phase 10

providers:
  claude:
    model: claude-3-5-sonnet-20241022
    daily_token_budget: 25000       # verify current free tier limit
    rpm_limit: 5                    # requests per minute (free tier)
    tpm_limit: 25000                # tokens per minute (free tier)
    context_window: 200000          # hard cap per request
    min_request_interval: 12.0      # seconds between requests (60 / rpm_limit, with buffer)
  gemini:
    model: gemini/gemini-1.5-flash
    daily_token_budget: 1500        # requests per day (free tier)
    rpm_limit: 15
    tpm_limit: 1000000
    context_window: 1000000
    min_request_interval: 4.0
  groq:
    model: groq/llama-3.1-70b-versatile
    daily_token_budget: 100000
    rpm_limit: 30
    tpm_limit: 6000
    context_window: 128000
    min_request_interval: 2.0
  fallback_order: [claude, gemini, groq]
  max_retries: 5                    # per provider before triggering fallback

ui:
  step_by_step: false               # pause between each plan step for micro-review
```

---

## Key Design Principles

**1. Abstract the engine from day one.** The `CodingEngine` ABC is the most important architectural decision. Never let the orchestrator import Aider directly.

**2. Design the API surface for two clients.** Every endpoint should make sense when called by your Svelte UI today *and* by RoboMesh's `roboserver` in Phase 8. If an endpoint feels too UI-specific, redesign it.

**3. Start simple, earn complexity.** While loop in Phase 1, LangGraph in Phase 3 when the async state management problem actually exists. SSE not WebSockets — use the simpler tool that fits the job.

**4. Tests run from Phase 2, not Phase 7.** The self-correction loop (code → test → fix → test) is the core value of an AI coding agent. Don't defer it.

**5. Ephemeral repos, persistent state.** The working repo clone is always temporary and wiped after each task. Session state, logs, and token budgets live in the mounted volume and survive restarts.

**6. Never resolve git conflicts autonomously.** On any git safety check failure, halt immediately, surface a clear alert, and wait for manual resolution. Autonomous conflict resolution is out of scope permanently.

**7. Token budgets in SQLite, not memory.** A container restart must not cause the agent to lose its daily token tally. Resets are keyed to calendar date in the configured timezone, not a 24-hour rolling window.

**8. Handle rate limits proactively, not reactively.** Don't rely solely on catching 429s — use minimum inter-request delays to avoid hitting RPM limits in the first place. When 429s do occur, use exponential backoff with jitter, respect `Retry-After` headers, and only trigger provider fallback after retries are exhausted. Context window errors are hard failures with no retry — truncate and log.

**9. Auth on every endpoint, no exceptions.** The agent holds GitHub credentials and can push code. A static bearer token in `.env` is enough — but no endpoint should be unauthenticated, even on a private network.

**10. Cap every loop that consumes credits.** The self-correction loop needs `max_self_correction_attempts`. The plan step loop needs `max_steps_per_session`. Uncapped loops will burn your entire daily budget on a problem the agent can't solve. Surface failures to the user rather than retrying forever.

**11. One task at a time, loudly reject conflicts.** The agent is single-threaded by design. A second task request while one is in flight returns HTTP 409. The scheduler skips its run if the agent is busy. Never queue silently — always be explicit about the conflict.

**12. Local-first, GitHub second.** Get the local loop working perfectly before adding any GitHub complexity. The GitHub integration (Phase 5) is additive — the core workflow doesn't depend on it.

---

## Existing Tools to Study (not build from)

| Tool | What to learn from it |
|---|---|
| [Aider](https://aider.chat/) | Your coding engine. Read its Python API docs and `aider/coders/` source |
| [SWE-agent ACI](https://github.com/SWE-agent/SWE-agent) | How to build tool-based context for Phase 9 |
| [LangGraph docs](https://langchain-ai.github.io/langgraph/) | State machine patterns — introduced in Phase 3 |
| [LiteLLM docs](https://docs.litellm.ai/) | How to set up provider fallback chains and track usage |
| [RoboMesh roboserver](https://github.com/shaply/Robomesh) | Your own project — understand its robot protocol before Phase 8 |
