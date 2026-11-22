# World Watcher — Project Specs

> Status: **Specification/design only**. No implementation yet. Build starts only when user explicitly says: **"go for plan and implement"**.

## 1. Project Overview

**Name:** `world-watcher`  
**Python:** 3.11  
**Goal:** A real-time monitoring dashboard with async workers, AI analysis, alerts, and a voice assistant connected to real backend tools.

## 2. Repository Structure

```text
world-watcher/
├── backend/                  # FastAPI app + APIs + engine
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   ├── worker_engine/        # async worker engine
│   ├── ai/                   # provider-independent AI module
│   ├── alerts/               # rule engine, channels, SQLite
│   ├── voice/                # STT/AI/TTS voice pipeline
│   └── assistant/            # tool-calling + confirmations
├── frontend/                 # React + Vite dashboard
├── workers/                  # real source plugins (easy to extend)
│   ├── base.py
│   ├── registry.py
│   └── sources/
├── config/                   # centralized config
│   ├── __init__.py
│   └── settings.py
├── tests/
├── .env.example
├── .gitignore                # excludes .env
├── requirements.txt
├── Dockerfile                # TBD: single or split; compose planned
├── docker-compose.yml
└── README.md
```

## 3. Configuration & Secrets

- **All API keys/config read from `.env`** via centralized config system (`config/settings.py`).
- `.env.example` contains placeholders only; never real secrets.
- `.gitignore` excludes `.env`, `.env.*` (except `.env.example`), `__pycache__/`, `.venv/`, `node_modules/`, `dist/`, logs/caches as needed.
- **Planned hardening:** store API keys safely (preferred: encrypted in SQLite using master-password-derived key); redact secrets from logs/errors/responses.

**Open decision:** `pydantic-settings` (typed, recommended) vs plain `os.getenv`/`python-dotenv`.

## 4. Backend Worker Engine (asyncio)

Location: `backend/worker_engine/`

### Worker model
Each worker has:
- `id`
- `name`
- `task_type`
- `status`: `idle | running | done | error`
- `current_action` (text)
- `progress`: `0-100`

### Engine requirements
- **Concurrency:** up to **20 workers** running at the same time.
- **Job queue:** async queue; workers pull jobs.
- **Retry:** automatic retry on failure (**3 times**; exact attempt semantics TBD).
- **Timeout:** per-job timeout.
- **Progress:** workers report progress updates during execution.
- **Mock tasks:** initial implementation uses mock tasks that sleep and report progress.
- **Tests:** unit/integration tests for concurrency cap, state transitions, progress, retries, timeout, shutdown.

**Open decisions:** retry = 3 retries vs 3 total attempts; worker returns to `idle` after done/error; handler callable vs task-type registry; `pytest-asyncio`.

## 5. Frontend Dashboard

**Stack:** React + Vite  
**Style:** dark, professional, terminal-style dashboard.

### UI components
- **Worker grid/cards:** status, current action, progress bar, name/id/task type.
- **Live event log:** bottom panel, real-time updates.
- **Stats bar:** running, done, errors (optionally idle/queued).
- **Loading states, clean theme, settings page** (hardening phase).

### Real-time
- Connect frontend to backend via **WebSocket** for instant updates.
- Use mock worker engine data initially; later real workers.
- Recommended WS messages: `snapshot`, `worker_update`, `event`, `stats`, `alert`.

**Open decisions:** JS vs TS; plain CSS/CSS modules vs Tailwind; event log cap; Vitest/RTL tests; Vite proxy vs hardcoded URLs.

## 6. Real Workers / Plugin System

Replace mock tasks with real workers in `workers/` as extensible plugins.

### Initial real workers
1. **News worker** — RSS feeds.
2. **Price worker** — free crypto/stock price API.
3. **Web page watcher** — detects changes on a URL.

### Safety/compliance
- **Respect `robots.txt`** before fetching pages/feeds where applicable.
- **Rate limiting** per host (token bucket / limiter).
- **Timeouts/retries** use engine policy; avoid retry spam on denied/4xx.
- **Easy plugin addition:** new source type by adding a module implementing the worker plugin contract and registering it.

**Open decisions:** price provider (CoinGecko, Yahoo/Stooq, etc.); long-running pollers vs scheduled one-shot jobs; page-watch state in-memory vs persisted JSON/SQLite; plugin discovery explicit vs auto; deps (`feedparser`, `httpx`, `aiolimiter`, `protego`, etc.).

## 7. AI Module (Provider-Independent)

Location: `backend/ai/`

### Provider selection
- Configurable in `.env`: `AI_PROVIDER=openai|anthropic|local` (or equivalent).
- Support OpenAI, Anthropic, and local model.

### Per-item analysis
For each item found by a worker:
- **Summarize in 2 sentences**.
- **Importance score 1-10**.
- **One-line reason**.

### Critical rules
- **Never let the AI calculate numbers; calculate them in plain Python code.**
  - Recommended: AI returns qualitative signals (urgency/impact/novelty, summary, reason); Python computes final 1-10 score and validates format.
  - Any numeric deltas/rates/counts computed in Python.
- **Cache results to save cost.** Cache key should include normalized content/item type/provider/model/prompt version.

**Open decisions:** local provider API (OpenAI-compatible vs Ollama-native); cache backend (SQLite recommended); inline analysis vs separate async analysis queue; official SDKs vs `httpx`.

## 8. Alert System

Location: `backend/alerts/`

### Rules
User can create rules such as:
- `"price drops 5%"`
- `"news mentions keyword X with importance 7 or higher"`

Recommended rule format: structured JSON conditions (ANDed), easy to extend.

### Channels
When a rule matches, send alert to:
- **Dashboard** (real-time WS)
- **Desktop notification**
- **Optionally Telegram**

### Storage
- **SQLite** for rules and alert history.
- Suggested tables: `rules`, `alert_history` (with timestamps, payload, delivery status, dedup/cooldown support).

### Behavior
- Evaluate enriched worker events (including Python-computed numeric fields and AI score/reason).
- Dedup/cooldown to prevent alert spam.
- Delivery failures logged; do not crash engine.

**Open decisions:** rule DSL vs structured JSON; AND-only vs AND/OR; desktop lib (`desktop-notifier` recommended); `aiosqlite` vs `sqlite3`; rule management UI now vs API only; cooldown semantics.

## 9. Real-Time Voice Assistant

Location: `backend/voice/` + frontend voice UI/hook.

### Pipeline
1. **Microphone input** (browser).
2. **Speech-to-text** (Whisper).
3. **AI brain** (provider-independent).
4. **Text-to-speech**.

### Requirements
- **Any language:** detect user's language and reply in the same language.
- **Voice switching:** user can switch between male/female by settings or by saying **"change to a girl voice"** (and equivalent commands).
- **Interruptible:** allow interrupting while it speaks (barge-in/button; flush playback).
- **Low latency:** keep delay under ~**1.5 seconds** by streaming (STT chunks, LLM streaming, TTS chunk streaming). Instrument TTFA per stage.

**Open decisions:** `faster-whisper` local vs Whisper API; TTS provider (`edge-tts` recommended behind interface); barge-in VAD+button vs button-first; multilingual command detection scope; AI brain chat-only vs dashboard-aware.

## 10. Voice Assistant Tool Calling / System Actions

Connect voice assistant to real backend functions via tool calling.

### Example commands
- `"start 10 news workers"`
- `"what happened today?"`
- `"show alerts"`
- `"stop all workers"`

### Safety policy
- **Use tool calling** so AI runs real backend functions through an allowlisted registry.
- **Ask for confirmation before any action that is destructive or costs money.**
- Pending actions expire; confirm/cancel by voice and/or dashboard buttons.
- Audit log for proposed/confirmed/cancelled/executed actions.

### Implementation notes
- Validate tool args with Pydantic schemas.
- "What happened today?" should use Python-computed aggregates from SQLite; AI narrates only.
- "Show alerts" may return data and optionally trigger dashboard focus/filter.

**Open decisions:** when to confirm `start_workers`; voice-only vs voice+UI confirmation; native tool-calling + JSON fallback; daily summary scope; show-alerts behavior.

## 11. Security, Reliability, Deployment, UI Polish

### Auth / first run
- Login with password set on **first run**.
- Single-user auth; password hashed (Argon2id recommended).
- Session cookie (HttpOnly/SameSite) or equivalent; protect REST + WS.

### API keys
- Store API keys safely; preferred encrypted-at-rest in SQLite, decrypted in memory after login.
- Masked in UI; never expose raw secrets.

### Observability / errors
- **Logging:** structured logs, request IDs, secret redaction, rotating file/console.
- **Error handling:** consistent API errors, no stack traces/secrets to clients; frontend error boundaries/toasts/reconnect states.

### Docker
- Add **Dockerfile** and **docker-compose.yml**.
- Volumes for SQLite/data/logs/cache; env-file support.
- Desktop notifications may be unavailable in containers; fallback to dashboard.

### UI improvements
- Clean dark theme, loading states, settings page.
- Settings: password change, API keys, AI provider/model, voice settings, Telegram, alert defaults.

### README
- Short setup steps: local Python 3.11 + Node, `.env`, first-run password, Docker Compose, troubleshooting.

**Open decisions:** encrypted SQLite secrets vs `.env`-only; cookie session vs JWT; two-service compose vs single image; Docker desktop notification fallback.

## 12. Testing & Quality Gates

- **Tests required** for worker engine; add tests for real workers, AI parsing/scoring/cache, alerts, auth, assistant tool policies as features land.
- Mock external APIs/network/TTS/STT/providers in tests.
- **Final review pass:** bugs, security problems, slow code; run tests, fix failures, report remaining improvements.

## 13. Implementation Order (Suggested)

1. Scaffold project structure + config + `.env.example` + README + `.gitignore`.
2. Async worker engine + mock tasks + tests.
3. FastAPI WS/API + React dashboard.
4. Real worker plugins (news/price/page-watch) + robots/rate limiting.
5. AI module + caching + Python scoring.
6. Alert rules/history/channels.
7. Voice assistant streaming pipeline.
8. Tool-calling assistant actions + confirmations.
9. Auth/secrets/logging/error handling/settings/Docker/UI polish.
10. Full review, test run, fixes, improvement report.

## 14. Open Questions Before Implementation

- Confirm scaffold/config/frontend choices from Section 2-5.
- Confirm worker engine semantics from Section 4.
- Confirm real-worker providers/state/deps from Section 6.
- Confirm AI scoring/provider/cache integration from Section 7.
- Confirm alert rule format/channels/storage UX from Section 8.
- Confirm voice stack/latency tradeoffs from Section 9.
- Confirm tool confirmation/UX/scope from Section 10.
- Confirm security/Docker scope from Section 11.

**Implementation trigger:** user says **"go for plan and implement"** (optionally with decisions).