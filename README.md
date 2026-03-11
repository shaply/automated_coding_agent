# AutoDev

**An automated, human-in-the-loop AI coding agent.**

AutoDev is a scheduled program that uses your free daily AI credits to make incremental, reviewed progress on a project of your choice. You stay in control at every key decision point — the AI does the work, you steer the direction and approve the results.

## How it works

1. **Plan**: AutoDev reads your GitHub issues (or accepts a manual task) and generates a step-by-step implementation plan.
2. **Review**: You review the plan in the browser, add comments, and approve.
3. **Code**: AutoDev implements the plan step-by-step using [Aider](https://aider.chat/), running tests after every step and self-correcting.
4. **Review again**: You see the final diff in the browser and approve or reject.
5. **Ship**: On approval, AutoDev pushes a branch and opens a PR on GitHub.

## Architecture

```text
AutoDev (Python + FastAPI + Svelte)
├── backend/          Python + FastAPI orchestrator
│   ├── api/          REST endpoints + SSE streaming
│   ├── orchestrator/ Workflow, planner, session state
│   ├── engine/       CodingEngine ABC + AiderEngine
│   ├── integrations/ LiteLLM, SQLite usage, GitHub, Git
│   └── prompts/      Prompt templates
└── frontend/         Svelte + TypeScript review UI
```

## Deployment

AutoDev runs on a mini PC as a persistent Docker container, accessible remotely via Tailscale.

```text
Mini PC (always on)
├── Docker: autodev-backend  (Python + FastAPI, port 8000)
└── Docker: autodev-frontend (Svelte, port 5173)
```

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/autodev.git
cd autodev
```

### 2. Set up environment variables

Set up backend environment variables.

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in:

```ini
# Required
AUTODEV_API_TOKEN=your-random-secret     # UI password — generate with: openssl rand -hex 32
ANTHROPIC_API_KEY=sk-ant-...             # Claude API key

# Optional (GitHub integration)
GITHUB_TOKEN=ghp_...                     # Personal access token for the bot account (see below)

# Optional (additional LLM providers)
# GEMINI_API_KEY=...
# GROQ_API_KEY=...
```

Edit `backend/config.yaml` to set your target GitHub repo, schedule, and provider preferences:

```yaml
project:
  github_repo: your-username/your-repo
  github_assignee: your-bot-github-username  # only this user's issues are auto-picked
  base_branch: main
  run_tests: false     # set true if the repo has a test suite
```

Set up frontend environment variables.

```bash
cp frontend/.env.example frontend/.env
```

Open `frontend/.env` and fill in:

```ini
# Required
VITE_API_URL=http://localhost:8000    # If pulling up website on another computer, then you need to set this address to the address of your mini PC
VITE_API_TOKEN=change-me-to-match-AUTODEV_API_TOKEN   # Should be same as AUTODEV_API_TOKEN in backend/.env
```

### 3. GitHub bot account (optional but recommended)

To avoid the agent working on issues you're already handling:

1. Create a **separate GitHub account** for the bot (e.g., `myproject-bot`)
2. No 2FA is needed — generate a **Personal Access Token** instead:
   - GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
   - Scopes: `Contents: Read & Write`, `Pull requests: Read & Write`, `Issues: Read`
3. Set `GITHUB_TOKEN` in `backend/.env` to that token
4. Set `github_assignee` in `config.yaml` to the bot's GitHub username
5. Assign issues to the bot account when you want AutoDev to work on them — unassign to claim them yourself

### 4. Run in Docker (recommended)

```bash
docker compose up -d
```

Access the UI at `http://localhost:5173`.

With Tailscale: `http://your-mini-pc.tailnet:5173` from anywhere.

### 5. Run locally (development)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
aider-install         # installs aider-chat — required once after pip install
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Tech Stack

| Component | Tool |
| --- | --- |
| Agent language | Python 3.11+ |
| LLM routing | LiteLLM (Claude → Gemini → Groq fallback) |
| Coding engine | Aider (via Python API) |
| Backend API | FastAPI + SSE |
| Frontend | Svelte + TypeScript |
| GitHub integration | PyGitHub + GitPython |
| Scheduling | APScheduler |
| Token budgets | SQLite |
| Deployment | Docker + docker-compose |
| Remote access | Tailscale |

## Implementation Phases

- [x] **Phase 1** — Foundation: CLI loop, Aider engine, LiteLLM routing, session state
- [x] **Phase 2** — Planning loop + per-step test execution + self-correction
- [x] **Phase 3** — Docker + FastAPI backend + ephemeral clones + git safety
- [x] **Phase 4** — Svelte frontend review UI
- [x] **Phase 5** — GitHub integration (issues → PRs)
- [x] **Phase 6** — Scheduler + multi-provider credit routing + log viewer
- [ ] **Phase 7** — Implementation controls (step-by-step mode, AI self-review)
- [ ] **Phase 8** — RoboMesh integration
- [ ] **Phase 9** — Context intelligence upgrade
- [ ] **Phase 10** — Custom coding engine

## Long-Term Vision

AutoDev registers as a robot in [RoboMesh](https://github.com/shaply/Robomesh), a robot management system. RoboMesh becomes the single dashboard for everything — physical robots and the coding agent alike.

## Security

Every API endpoint requires a Bearer token (`AUTODEV_API_TOKEN` in `.env`). Never expose the backend port without authentication — the agent holds GitHub credentials and can push code.

## License

MIT
