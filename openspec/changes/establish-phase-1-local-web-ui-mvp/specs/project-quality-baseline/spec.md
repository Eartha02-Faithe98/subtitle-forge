## ADDED Requirements

### Requirement: Automated current-phase verification
The repository SHALL provide documented automated commands that verify backend and frontend behavior, static quality checks, the frontend-to-backend interaction, and the complete Phase 1 media-to-artifact workflow while retaining Phase 0 regression coverage.

#### Scenario: Run the Phase 1 verification suite
- **WHEN** a developer runs the documented verification commands with the declared local test prerequisites available
- **THEN** the commands verify the Phase 0 baseline plus Phase 1 intake, job transitions, timestamp preservation, local provider contracts, artifact generation, downloads, UI progress, and failure handling, returning non-zero for any failed check

#### Scenario: Run tests without external media or model availability
- **WHEN** deterministic unit and integration tests run in an isolated development environment
- **THEN** provider, media, YouTube, and model boundaries can be replaced with controlled test doubles so the core verification suite does not depend on live YouTube or non-deterministic AI output

### Requirement: Accurate phase-aware project documentation
The README SHALL explain the product positioning, completed Phase 0 and Phase 1 features, deferred features, Windows 11 prerequisites including local media and AI dependencies, model setup, storage and cleanup behavior, configuration, startup, testing, troubleshooting, security, architecture, and development workflow without presenting unfinished functionality as complete.

#### Scenario: Follow the Windows Phase 1 guide
- **WHEN** a new contributor follows the README on a supported Windows 11 environment
- **THEN** the contributor can configure, start, exercise, and test the Local Web UI workflow and can distinguish optional or deferred capabilities from required local prerequisites

### Requirement: Evidence-based Phase 1 completion report
The project MUST NOT report Phase 1 as complete unless a Windows 11 user can start the application, submit each supported source type, run the documented local pipeline without a paid API, observe progress, obtain every required output, download the artifacts, and pass all automated and regression checks.

#### Scenario: Report successful Phase 1 completion
- **WHEN** all Phase 1 acceptance criteria have been verified
- **THEN** the completion report records the phase, status, implemented scope, test evidence, known issues, changed files, run instructions, and a PASS result with evidence for every criterion

#### Scenario: A Phase 1 criterion fails
- **WHEN** any required source, local processing stage, output, download, progress behavior, security check, or regression cannot be verified or fails
- **THEN** the completion report marks Phase 1 incomplete and identifies the failed or unverified criterion

## REMOVED Requirements

### Requirement: Automated Phase 0 verification
**Reason**: Verification must now cover the current Phase 1 workflow in addition to the retained foundation checks.

**Migration**: Keep all Phase 0 checks as regressions inside the expanded current-phase verification gate.

### Requirement: Accurate project documentation
**Reason**: Phase 0-only setup and capability claims no longer describe the Phase 1 local media workflow.

**Migration**: Expand the README in place and continue labeling all deferred features truthfully.

### Requirement: Evidence-based Phase completion report
**Reason**: The original requirement governs Phase 0 completion only and cannot establish Phase 1 readiness.

**Migration**: Preserve the Phase 0 report and add an evidence-based Phase 1 completion report governed by the new requirement.
