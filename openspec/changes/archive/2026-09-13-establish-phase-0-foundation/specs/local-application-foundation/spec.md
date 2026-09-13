## Purpose

Defines the observable local web and API baseline that proves Subtitle Forge can run and communicate correctly before media-processing features are added.

## ADDED Requirements

### Requirement: Local application startup
The system SHALL provide a documented way for a Windows 11 developer to start the frontend and backend locally, with the frontend available on a configured local port that defaults to `3000` and the backend available on its configured local address.

#### Scenario: Start with documented defaults
- **WHEN** a developer installs the documented prerequisites and follows the local startup instructions
- **THEN** the frontend and backend start without requiring any paid service, API key, database, or media-processing dependency

### Requirement: Backend health contract
The backend SHALL expose `GET /health` as an unauthenticated health endpoint that returns HTTP `200` and a JSON body containing `status: "ok"` while the application is ready to serve requests.

#### Scenario: Healthy backend
- **WHEN** a client sends `GET /health` to a running backend
- **THEN** the backend returns HTTP `200` with JSON containing `status: "ok"`

### Requirement: Phase 0 UI shell
The frontend SHALL render a usable Subtitle Forge application shell that identifies the product as an AI bilingual media knowledge tool and distinguishes the current foundation from features planned for later phases.

#### Scenario: Open the local web UI
- **WHEN** a user opens the running frontend in a supported modern browser
- **THEN** the page displays the Subtitle Forge identity, the current Phase 0 foundation state, and no claim that Phase 1 media or AI features are available

### Requirement: Frontend reports backend connectivity
The frontend SHALL call the configured backend health endpoint and present a human-readable connectivity state without exposing internal stack traces or filesystem paths.

#### Scenario: Backend is reachable
- **WHEN** the frontend receives a successful health response from the backend
- **THEN** the UI reports that the backend is connected

#### Scenario: Backend is unavailable
- **WHEN** the frontend cannot reach the backend or receives an invalid health response
- **THEN** the UI remains usable and reports that the backend is unavailable with guidance to start or check the local backend

### Requirement: Local cross-origin access is constrained
When the frontend and backend use different local origins, the backend MUST accept browser requests only from explicitly configured frontend origins and MUST NOT use an unrestricted wildcard origin when credentials are enabled.

#### Scenario: Configured frontend origin
- **WHEN** the browser sends a health request from an allowed local frontend origin
- **THEN** the backend returns the response with the access-control headers required by the browser

#### Scenario: Unconfigured origin
- **WHEN** a browser request originates from an origin not present in the configured allowlist
- **THEN** the backend does not grant that origin cross-origin access
