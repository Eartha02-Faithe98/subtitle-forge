## Context

The repository is greenfield: outside OpenSpec it contains only `CODEX_DEVELOPMENT_SPEC.md`, and it is not currently recognized as a Git repository. The product specification fixes the Phase 0 stack direction as a React/Next.js/TypeScript frontend and Python/FastAPI backend, with Windows 11 as the primary development environment. See `proposal.md` for motivation and the three delta specs for behavioral requirements.

Phase 0 must prove a real local frontend/backend seam while avoiding Phase 1 dependencies such as FFmpeg, Whisper, LLM SDKs, persistence, and job processing. The layout must remain simple enough for local development while keeping business services separable when later phases arrive.

## Goals / Non-Goals

**Goals:**

- Establish clear frontend and backend package boundaries with repeatable dependency installation.
- Provide a typed, minimal health contract exercised from the browser-facing UI.
- Make environment ownership explicit, especially the boundary between browser-public and backend-only configuration.
- Provide automated unit, contract, and browser-level verification proportional to the small Phase 0 surface.
- Make Windows startup and verification convenient without making PowerShell the only supported way to run each component.

**Non-Goals:**

- Define media, transcript, subtitle, provider, credential-store, job, or database domain models.
- Add placeholder abstractions for future providers before a Phase 1 use case exists.
- Add containers, Redis, distributed workers, authentication, telemetry services, or production deployment configuration.
- Guarantee one-command production packaging; Phase 0 targets a development-mode local web application.

## Decisions

### Use a two-package repository with explicit boundaries

Create `frontend/` for the Next.js application and `backend/` for the installable FastAPI application, plus root `scripts/` for cross-component developer checks. Keep frontend and backend dependency manifests inside their respective directories instead of introducing a JavaScript monorepo manager.

This is simpler for a Python/Node split and leaves later domain services in the backend package rather than creating speculative top-level service packages. A single mixed package was rejected because it obscures runtime and dependency boundaries; workspaces and monorepo orchestration were rejected as unnecessary Phase 0 machinery.

### Use a thin Next.js App Router shell and a versionable FastAPI application package

The frontend uses TypeScript and the Next.js App Router with a small client-side health-status component. The backend exposes an application factory and router with `GET /health`; future API groups can adopt versioned paths when feature APIs exist without changing the foundation health probe.

Using a static HTML frontend was rejected because the confirmed stack is Next.js and Phase 1 needs interactive workflow state. Building media-oriented pages or provider interfaces now was rejected because no Phase 0 behavior exercises them.

### Call the backend directly from the browser through a configurable public base URL

The health component reads a non-secret public API base URL, calls `${baseUrl}/health`, validates the response shape, and maps success, loading, and failure to explicit UI states. FastAPI uses an environment-configured CORS allowlist with the local frontend origin as its safe default.

A Next.js server proxy was considered but rejected for Phase 0 because it adds another server-side hop without yet protecting credentials or aggregating APIs. The direct seam is easier to observe and test; later changes can introduce a backend-for-frontend if a concrete security or deployment requirement appears.

### Keep configuration owned by each runtime

Backend settings are parsed and validated in one settings module from environment variables and an optional ignored local environment file. Frontend-public settings use the framework's public-variable convention and contain only the backend base URL. A root `.env.example` documents the complete Phase 0 surface, while component documentation states where each value is consumed.

Scattered environment reads were rejected because they make validation and secret review difficult. A database-backed settings system and OS credential store are deferred until Phase 1 introduces persistent provider credentials.

### Use layered verification with a small end-to-end smoke test

Backend tests exercise the health route and settings validation. Frontend component tests exercise loading, connected, invalid-response, and unavailable states. Static checks cover Python lint/type policy and TypeScript lint/type checking. A browser smoke test starts both development servers, opens the frontend, and asserts that the UI reaches the connected state against the real backend.

Relying only on mocked frontend tests was rejected because it would not prove the configured browser-to-API seam. A broad end-to-end suite was rejected because Phase 0 has only one cross-runtime interaction.

### Provide standard component commands plus Windows orchestration scripts

Each component remains runnable with standard `npm` and Python module commands. PowerShell scripts coordinate local development and verification from the repository root, check prerequisites, propagate child-process failures, and clean up processes they start.

Requiring Docker was rejected because it conflicts with the local-first simplicity goal and adds a prerequisite. A custom long-running process manager was rejected in favor of short, inspectable scripts.

### Initialize source-control and open-source metadata without committing

Implementation initializes Git metadata if absent, adds a comprehensive `.gitignore`, retains a safe `.env.example`, and supplies README, contribution guidance, and a permissive open-source license. The apply workflow will not create a commit unless separately authorized.

MIT is selected as the default permissive license because the specification requires open source but does not impose reciprocal licensing. If the owner prefers a different license, replacing the license text is isolated and does not affect runtime behavior or the task sequence.

## Risks / Trade-offs

- [Direct browser-to-backend calls require CORS and expose the non-secret API location] → Centralize the base URL, use an explicit origin allowlist, and keep secrets entirely server-side.
- [Two language ecosystems increase setup steps on Windows] → Pin dependencies, document supported versions, and provide root PowerShell helpers while retaining standard component commands.
- [Development-server startup timing can make the smoke test flaky] → Poll bounded health URLs for readiness, capture child-process output on failure, and always clean up spawned processes.
- [Greenfield tool-version choices can age quickly] → Record supported runtime ranges, commit lock data where appropriate, and let automated checks detect incompatibility instead of coupling specs to exact library versions.
- [The specification file contains visible encoding corruption in several diagrams/examples] → Treat intact prose and Phase 0 acceptance criteria as authoritative; do not reproduce corrupted glyphs in generated documentation.
- [Initializing Git changes repository metadata outside normal source files] → Make initialization idempotent and do not stage or commit without explicit authorization.

## Migration Plan

1. Initialize the repository metadata and safety files before installing or generating build output.
2. Scaffold the backend package, settings, health route, and backend tests; verify them independently.
3. Scaffold the frontend shell and health client with unit tests; verify it independently.
4. Add the bounded browser smoke test and root Windows helper scripts, then verify the real cross-component seam.
5. Add README, license, and contribution guidance that reflect only verified functionality.
6. Run the full verification suite and manually review the Phase 0 acceptance criteria. If a step fails, keep the change uncommitted and correct forward; rollback consists of removing only the newly introduced Phase 0 files while preserving the product and OpenSpec documents.
