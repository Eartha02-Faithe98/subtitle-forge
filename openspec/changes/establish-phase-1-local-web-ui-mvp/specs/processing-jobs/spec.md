## Purpose

Defines the explicit local job lifecycle and progress contract that keeps long-running media work observable, recoverable, and understandable in the browser.

## ADDED Requirements

### Requirement: Processing begins behind a job boundary
The system SHALL create a unique local job before beginning long-running work and SHALL return its identifier promptly enough for the client to begin status monitoring without waiting for the complete pipeline.

#### Scenario: Create a processing job
- **WHEN** a valid source and local processing options are submitted
- **THEN** the system returns a job identifier and an initial `PENDING` status before the final artifacts are available

### Requirement: Job transitions are explicit and valid
The system SHALL model applicable processing stages using `PENDING`, `DOWNLOADING`, `EXTRACTING_AUDIO`, `TRANSCRIBING`, `TRANSLATING`, `GENERATING_SUBTITLES`, `GENERATING_SUMMARY`, `COMPLETED`, and `FAILED`, and MUST reject invalid or backward terminal transitions.

#### Scenario: Process an uploaded file successfully
- **WHEN** an MP3 or MP4 job succeeds
- **THEN** it advances from `PENDING` through the applicable stages without entering `DOWNLOADING` and ends at `COMPLETED`

#### Scenario: Process YouTube successfully
- **WHEN** a YouTube job succeeds
- **THEN** it includes `DOWNLOADING`, advances through each later applicable stage, and ends at `COMPLETED`

#### Scenario: A stage fails
- **WHEN** any processing stage encounters an unrecoverable error
- **THEN** the job transitions once to `FAILED` and cannot later be reported as `COMPLETED`

### Requirement: Progress is observable
The system SHALL expose the current stage, a human-readable stage label, completed-stage information, and a bounded progress value from 0 through 100 for each job.

#### Scenario: Poll an active job
- **WHEN** the client requests status for a running job
- **THEN** the response identifies the active stage and reports progress that does not move backward across completed stages

#### Scenario: Poll a completed job
- **WHEN** the client requests status for a completed job
- **THEN** the response reports `COMPLETED`, progress 100, and the available result manifest

### Requirement: Job failures are safe and actionable
Failed jobs SHALL expose a stable error category, the stage that failed, and a concise recovery message while retaining detailed diagnostics only in sanitized local logs.

#### Scenario: Display a processing failure
- **WHEN** a job fails because of invalid media, unavailable source, missing local dependency, or local provider failure
- **THEN** the client receives a category-specific message and does not receive a stack trace, command line, credential, or internal filesystem path

### Requirement: Local job records survive application restart
The system SHALL persist job state and artifact metadata locally; interrupted non-terminal jobs MUST be marked failed on restart, while completed artifact metadata SHALL remain available when its files still exist.

#### Scenario: Restart after completion
- **WHEN** the backend restarts after a job completed and its artifacts remain in managed storage
- **THEN** the job status and download manifest remain available

#### Scenario: Restart during processing
- **WHEN** the backend restarts while a job is in a non-terminal processing state
- **THEN** the job is marked `FAILED` with an interruption message rather than remaining indefinitely active
