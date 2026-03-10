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

```
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

```
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

### 2. Configure

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys and secrets
```

Edit `backend/config.yaml` to set your target GitHub repo, schedule, and provider preferences.

### 3. Run locally (development)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

### 4. Run in Docker (production)

```bash
docker compose up -d
```

Access the UI at `http://localhost:5173` or `http://your-mini-pc.tailnet:5173` via Tailscale.

## Tech Stack

| Component | Tool |
|---|---|
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
- [ ] **Phase 2** — Planning loop + per-step test execution
- [ ] **Phase 3** — Docker + FastAPI backend + LangGraph
- [ ] **Phase 4** — Svelte frontend review UI
- [ ] **Phase 5** — GitHub integration (issues → PRs)
- [ ] **Phase 6** — Scheduler + multi-provider credit routing
- [ ] **Phase 7** — Implementation controls (mid-task comment injection)
- [ ] **Phase 8** — RoboMesh integration
- [ ] **Phase 9** — Context intelligence upgrade
- [ ] **Phase 10** — Custom coding engine

## Long-Term Vision

AutoDev registers as a robot in [RoboMesh](https://github.com/shaply/Robomesh), a robot management system. RoboMesh becomes the single dashboard for everything — physical robots and the coding agent alike.

## Security

Every API endpoint requires a Bearer token (`AUTODEV_API_TOKEN` in `.env`). Never expose the backend port without authentication — the agent holds GitHub credentials and can push code.

## License

MIT
