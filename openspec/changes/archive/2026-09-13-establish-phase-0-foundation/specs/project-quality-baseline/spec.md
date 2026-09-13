## Purpose

Defines the verification, documentation, and open-source project baseline needed to reproduce Phase 0 and make truthful completion claims.

## ADDED Requirements

### Requirement: Automated Phase 0 verification
The repository SHALL provide documented automated commands that verify backend behavior, frontend behavior, static quality checks, and the frontend-to-backend health interaction.

#### Scenario: Run the verification suite
- **WHEN** a developer runs the documented verification commands in a correctly prepared environment
- **THEN** the commands complete non-interactively with a non-zero exit code for any failed check and a zero exit code only when all selected checks pass

### Requirement: Health interaction regression coverage
Automated tests MUST cover both a successful backend health response and an unavailable or invalid backend response as presented by the frontend.

#### Scenario: Detect a broken health contract
- **WHEN** the backend health response no longer satisfies the documented contract or the frontend no longer handles it correctly
- **THEN** at least one automated verification check fails

### Requirement: Accurate project documentation
The README SHALL explain the product positioning, completed Phase 0 features, deferred features, Windows 11 prerequisites, configuration, startup, testing, security considerations, architecture outline, provider roadmap, and development workflow without presenting unfinished functionality as complete.

#### Scenario: Follow the Windows development guide
- **WHEN** a new contributor follows the README on a supported Windows 11 environment
- **THEN** the contributor can configure, start, and test the Phase 0 frontend and backend using the documented commands

### Requirement: Open-source contribution metadata
The repository SHALL include an open-source license and contribution guidance covering local setup, verification expectations, secret handling, and scope discipline.

#### Scenario: Review contribution requirements
- **WHEN** a prospective contributor opens the repository
- **THEN** the license terms and the checks expected before submitting a change are discoverable from top-level project documentation

### Requirement: Evidence-based Phase completion report
The project MUST NOT report Phase 0 as complete unless startup, frontend loading, backend loading, frontend/backend communication, the health endpoint, secret-safety checks, and automated tests have all been verified.

#### Scenario: Report successful Phase 0 completion
- **WHEN** all Phase 0 acceptance criteria have been verified
- **THEN** the completion report records the phase, status, implemented scope, test evidence, known issues, changed files, run instructions, and PASS results for the acceptance criteria

#### Scenario: Acceptance criterion fails
- **WHEN** any Phase 0 acceptance criterion cannot be verified or fails
- **THEN** the completion report marks Phase 0 incomplete and identifies the failed or unverified criterion
