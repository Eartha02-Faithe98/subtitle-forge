## Why

Subtitle Forge currently contains only its product specification and OpenSpec configuration, so there is no runnable foundation on which to build the local-first bilingual media workflow. Phase 0 establishes a small, testable Windows-oriented web application baseline before any Phase 1 media or AI capability is introduced.

## What Changes

- Establish a runnable local application with a Next.js/TypeScript frontend and FastAPI/Python backend.
- Provide a basic Subtitle Forge UI shell that can confirm communication with the backend.
- Expose a backend health endpoint and make its status observable from the frontend.
- Add environment-based application configuration with a safe example file and repository ignore rules for local secrets and generated artifacts.
- Add automated frontend and backend tests covering startup-critical behavior and frontend/backend communication.
- Add the initial open-source project documentation and metadata needed to install, run, test, and understand the current Phase 0 scope on Windows 11.
- Explicitly defer media ingestion, AI providers, transcription, translation, summaries, subtitles, persistent credentials, background jobs, and SaaS functionality to later phases.

## Capabilities

### New Capabilities

- `local-application-foundation`: A locally runnable web UI and API foundation, including the UI shell, health endpoint, and verified frontend/backend communication.
- `configuration-security-baseline`: Environment-driven configuration and repository safeguards that keep real credentials and local artifacts out of source control and client-visible code.
- `project-quality-baseline`: Automated verification plus accurate open-source documentation and metadata for developing and running the Phase 0 application.

### Modified Capabilities

None.

## Impact

- Introduces the initial `frontend/`, `backend/`, test, documentation, and development-script structure in an otherwise greenfield repository.
- Adds Node.js and Python development dependencies for Next.js, FastAPI, configuration, testing, linting, and type checking.
- Defines a small HTTP contract for backend health reporting and frontend connectivity checks.
- Adds repository-level `.gitignore`, `.env.example`, README, license, and contributing guidance.
- Does not introduce a database, FFmpeg, Whisper, Ollama, cloud AI SDKs, queues, authentication, or production hosting infrastructure.
