## 1. Repository and Safety Foundation

- [x] 1.1 Initialize Git metadata when absent without staging or committing files, then verify `git rev-parse --is-inside-work-tree` returns `true`.
- [x] 1.2 Add the root `.gitignore` for local environment files, Python and Node dependencies/build output, caches, logs, test artifacts, editors, and temporary runtime data; verify representative ignored files are excluded while `.env.example` remains trackable with `git check-ignore`.
- [x] 1.3 Add a root `.env.example` containing only Phase 0 non-secret defaults and placeholders, then verify a repository secret scan and manual review find no working credentials.

## 2. Backend Foundation

- [x] 2.1 Create the installable `backend/` Python package, dependency metadata, application factory, and standard development commands; verify a clean virtual environment can install the package and import the FastAPI application.
- [x] 2.2 Implement centralized backend settings for host, port, environment, and allowed frontend origins with safe localhost defaults and validation; verify unit tests cover defaults, environment overrides, and invalid values without leaking input secrets.
- [x] 2.3 Configure CORS from the validated origin allowlist and verify backend tests allow the configured frontend origin while omitting access permission for an unconfigured origin.
- [x] 2.4 Implement unauthenticated `GET /health` returning HTTP `200` and `{"status":"ok"}`, then verify the endpoint contract through FastAPI integration tests.
- [x] 2.5 Add backend linting, formatting-check, type-checking, and test commands; verify all backend quality commands pass from the documented working directory.

## 3. Frontend Foundation

- [x] 3.1 Create the `frontend/` Next.js App Router project with TypeScript, pinned lock data, and standard development/build commands; verify dependency installation, type checking, and a production build succeed.
- [x] 3.2 Implement a centralized non-secret public API base URL with a safe localhost default and URL validation; verify tests cover the default, a valid override, and invalid configuration behavior.
- [x] 3.3 Build the responsive Subtitle Forge Phase 0 application shell with accurate product positioning and deferred-feature messaging; verify component tests and a production build render the expected identity without claiming Phase 1 functionality.
- [x] 3.4 Implement the health-status client with loading, connected, invalid-response, and unavailable states plus actionable non-sensitive failure guidance; verify component tests cover every state and never render raw stack traces or filesystem paths.
- [x] 3.5 Add frontend linting, formatting-check, type-checking, and unit-test commands; verify all frontend quality commands pass non-interactively.

## 4. Local Orchestration and Integration

- [x] 4.1 Add a root PowerShell development script that checks prerequisites, starts the backend and frontend with documented environment values, propagates startup failures, and cleans up only the processes it launches; verify both local URLs become reachable and terminate cleanly after the script stops.
- [x] 4.2 Add a bounded browser smoke test that launches both components, waits for readiness, opens the frontend, and asserts the real UI reaches the backend-connected state; verify the test passes repeatedly and fails when the backend health contract is intentionally unavailable.
- [x] 4.3 Add a root PowerShell verification script that runs backend checks, frontend checks, and the browser smoke test while preserving the first failing exit status; verify it returns zero for the passing suite and non-zero for an induced failing check.

## 5. Open-Source Documentation

- [x] 5.1 Add the MIT `LICENSE` and `CONTRIBUTING.md` with local setup, required checks, secret handling, and phase-scope guidance; verify both are linked and discoverable from the README.
- [x] 5.2 Write the README with product positioning, verified Phase 0 features, explicitly deferred roadmap items, Windows 11 prerequisites, configuration, startup, testing, architecture, security, AI-provider direction, and development workflow; verify every documented command succeeds in a clean local setup and no unfinished feature is described as available.

## 6. Phase 0 Acceptance Verification

- [x] 6.1 Run the complete backend, frontend, static, build, and browser verification suite from a clean dependency installation; record the commands and passing results for the Phase 0 report.
- [x] 6.2 Start the application through the documented Windows workflow and verify the frontend loads, the backend loads, `GET /health` returns the required JSON, and the UI reports a real backend connection.
- [x] 6.3 Review tracked and untracked files, ignore behavior, frontend build output, logs, and HTTP errors for credentials or sensitive paths; verify no secrets are committed or exposed and document any remaining known issue.
- [x] 6.4 Produce the required Phase 0 completion report with status, implemented scope, tests, known issues, changed files, run instructions, and a PASS/FAIL result for every acceptance criterion; verify Phase 0 is not marked complete unless all criteria pass.
