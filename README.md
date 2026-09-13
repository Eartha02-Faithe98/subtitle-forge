# Subtitle Forge

Subtitle Forge is an open-source **AI bilingual media knowledge tool**. Its long-term goal is to turn video and audio into bilingual, timestamp-aware subtitles, transcripts, summaries, and searchable knowledge with evidence linked to the original media.

> Turn any video or audio into bilingual subtitles and knowledge.

## Current status: Phase 0 foundation

The repository currently provides only the tested application foundation:

- A responsive Next.js and TypeScript local web UI shell.
- A Python and FastAPI backend with `GET /health`.
- A visible browser-to-backend connection status with safe failure guidance.
- Explicit CORS allowlisting and environment-based local configuration.
- Backend and frontend unit, type, lint, format, build, and browser smoke checks.
- Windows PowerShell scripts for local startup and full verification.

Media upload, YouTube download, FFmpeg, Whisper, translation, summaries, subtitles, provider selection, API-key persistence, background jobs, and all SaaS features are **not implemented yet**. They begin in Phase 1 or later only after the preceding phase passes its acceptance criteria.

## Product direction

Subtitle Forge is designed around four priorities:

1. Preserve timestamps as first-class data.
2. Prefer local, open-source AI so a paid API is never mandatory.
3. Keep speech-to-text, translation, and summary providers independently selectable.
4. Share core business logic between the initial local application and a possible future SaaS deployment.

The planned provider architecture will support Local Whisper for speech-to-text and Ollama-compatible local models for translation and summaries, with optional bring-your-own-key cloud adapters. None of those adapters is part of Phase 0.

## Development setup

### Prerequisites

- Windows 11
- Git
- Python 3.11 or newer
- Node.js 20.9 or newer with npm
- Google Chrome for the Playwright smoke test

### 1. Create the backend environment

From the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
```

### 2. Install frontend dependencies

```powershell
Push-Location frontend
npm install
Pop-Location
```

The committed `package-lock.json` keeps frontend dependency resolution repeatable.

### 3. Configure local overrides

The defaults work on localhost without an API key. To customize them:

```powershell
Copy-Item .env.example .env
```

`.env` is ignored by Git. Never place real credentials in `.env.example`.

| Variable | Default | Runtime | Purpose |
| --- | --- | --- | --- |
| `SUBTITLE_FORGE_HOST` | `127.0.0.1` | Backend | Local API bind host |
| `SUBTITLE_FORGE_PORT` | `8000` | Backend | Local API port |
| `SUBTITLE_FORGE_ENVIRONMENT` | `development` | Backend | `development`, `test`, or `production` |
| `SUBTITLE_FORGE_ALLOWED_ORIGINS` | localhost ports 3000 | Backend | JSON array of explicit browser origins |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Browser | Public, non-secret backend origin |
| `FRONTEND_PORT` | `3000` | Startup script | Local Next.js port |

Only `NEXT_PUBLIC_*` values are delivered to browser JavaScript, so they must never contain secrets.

## Run locally

Start both components from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

Then open <http://127.0.0.1:3000>. The page reports **Backend connected** after `GET http://127.0.0.1:8000/health` returns:

```json
{"status":"ok"}
```

Press `Ctrl+C` in the development terminal to stop only the frontend and backend processes launched by the script. Startup logs are written to the ignored `runtime/` directory.

You can also run the components independently:

```powershell
# Terminal 1, repository root
backend\.venv\Scripts\python.exe -m uvicorn subtitle_forge_api.app:app --host 127.0.0.1 --port 8000

# Terminal 2
Push-Location frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Test and verify

Run the complete Phase 0 gate from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Individual checks are also available:

```powershell
# Backend
Push-Location backend
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\ruff.exe check .
.venv\Scripts\mypy.exe
.venv\Scripts\python.exe -m pytest -q
Pop-Location

# Frontend
Push-Location frontend
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run smoke
Pop-Location
```

The smoke test starts real local FastAPI and Next.js servers, opens installed Google Chrome at desktop and 375px mobile viewports, checks the visible backend connection, and verifies there is no horizontal overflow.

## Architecture

```text
Browser
  └─ Next.js UI (frontend/)
       └─ GET /health
            └─ FastAPI (backend/)
```

Phase 0 intentionally contains no media, AI-provider, persistence, queue, authentication, or SaaS modules. Those boundaries will be introduced only when a tested feature needs them.

## Security baseline

- Real environment files, virtual environments, dependencies, builds, logs, caches, browser traces, and temporary runtime data are ignored.
- The backend accepts browser access only from configured origins; wildcard CORS is rejected.
- Invalid configuration stops startup with validation errors.
- The frontend receives only a public API origin and never renders backend exceptions or local filesystem paths.
- Future credentials must stay server-side and must not appear in source, logs, HTTP errors, or frontend bundles.

## Roadmap

- **Phase 0 — Foundation:** local UI/API shell, configuration, tests, documentation.
- **Phase 1 — Local Web UI MVP:** YouTube, MP3, MP4, Local Whisper, Traditional Chinese translation, summaries, English/Chinese/bilingual SRT, downloads, and processing progress.
- **Phase 2 — More media sources:** article and website-video URLs.
- **Phase 3 — Knowledge layer:** projects, chapters, key points, and transcript search.
- **Phase 4 — RAG and timestamp-cited Q&A.**
- **Later — Web application and production SaaS architecture.**

Roadmap entries are plans, not claims of available functionality.

## Project documents

- [Development specification](CODEX_DEVELOPMENT_SPEC.md)
- [Contributing guide](CONTRIBUTING.md)
- [MIT License](LICENSE)
- [OpenSpec changes](openspec/changes/)

## License

Subtitle Forge is available under the [MIT License](LICENSE).
