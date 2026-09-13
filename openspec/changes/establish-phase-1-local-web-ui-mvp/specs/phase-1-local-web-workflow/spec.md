## Purpose

Defines the browser experience that connects supported media intake, local processing choices, observable progress, bilingual results, and downloads into one usable MVP.

## ADDED Requirements

### Requirement: The UI offers only Phase 1 source choices
The Local Web UI SHALL let the user choose YouTube URL, MP3 upload, or MP4 upload and SHALL keep those input modes mutually exclusive.

#### Scenario: Switch source type
- **WHEN** a user changes from one source type to another before submission
- **THEN** the form activates the selected input, clears stale validation for the prior mode, and submits only the selected source

### Requirement: Local processing options are understandable
The UI SHALL identify Local Whisper as the speech-to-text provider, offer Fast, Balanced, and Accurate performance profiles with plain-language tradeoffs, and identify the configured Ollama-compatible local translation and summary model without offering cloud providers in Phase 1.

#### Scenario: Configure a local job
- **WHEN** a user prepares a processing job
- **THEN** the form shows the selected Whisper profile and the local translation and summary configuration before processing starts

### Requirement: Invalid submission is explained before processing
The UI SHALL validate required source fields and obvious type or size constraints, SHALL preserve keyboard and screen-reader access to validation messages, and MUST NOT submit a known-invalid request.

#### Scenario: Submit an invalid form
- **WHEN** a user attempts to start without a valid selected source
- **THEN** processing does not start and focus or an accessible message identifies what must be corrected

### Requirement: Processing progress is presented continuously
After job creation, the UI SHALL monitor job status and present the active stage, overall progress, and completed stages until the job reaches `COMPLETED` or `FAILED`.

#### Scenario: Observe a running job
- **WHEN** the backend reports successive processing stages
- **THEN** the UI updates from downloading when applicable through extraction, transcription, translation, subtitle generation, and summary generation without requiring a page reload

#### Scenario: Backend status polling is temporarily unavailable
- **WHEN** a status request fails while the job is non-terminal
- **THEN** the UI reports that status cannot currently be refreshed and allows monitoring to resume without creating a duplicate job automatically

### Requirement: Results are reviewable and downloadable
The UI SHALL present completed English and Traditional Chinese transcripts, all three SRT variants, and both summaries with an individual download action for every artifact.

#### Scenario: Complete a job
- **WHEN** the backend reports a completed result manifest
- **THEN** the UI shows the bilingual result sections and seven corresponding download actions

### Requirement: Failures remain recoverable
The UI SHALL show the failed stage and actionable safe error message and SHALL let the user revise the source or local settings and intentionally start a new job.

#### Scenario: Processing fails
- **WHEN** a job reaches `FAILED`
- **THEN** the UI stops progress monitoring, displays recovery guidance, and does not expose raw backend diagnostics

### Requirement: The workflow is usable on supported local viewports
The Phase 1 workflow SHALL remain operable with keyboard navigation and on desktop and narrow mobile-width browser viewports without horizontal page overflow.

#### Scenario: Use a narrow viewport
- **WHEN** the workflow is opened at a 375-pixel-wide viewport
- **THEN** source controls, progress, results, and download actions remain readable and operable without horizontal scrolling
