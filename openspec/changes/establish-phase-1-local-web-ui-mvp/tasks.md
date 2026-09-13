## 1. Runtime Configuration and Dependencies

- [x] 1.1 Add and pin the Phase 1 backend dependencies for multipart uploads, yt-dlp, faster-whisper, and local HTTP provider calls, then verify a clean `backend/.venv` installation resolves without dependency conflicts.
- [x] 1.2 Extend backend settings with the managed data root, upload limit, tool timeouts, Whisper profile-to-model map, compute settings, Ollama base URL/model, prompt limits, polling metadata, and retention values; verify unit tests cover safe defaults and invalid or unsafe overrides.
- [x] 1.3 Extend `.env.example` with non-secret Phase 1 settings and verify secret-signature and frontend-public-variable tests prove that no model credentials or internal paths are browser-exposed.
- [x] 1.4 Add startup dependency/readiness checks for FFmpeg, ffprobe, the selected Whisper model, and the Ollama-compatible endpoint while keeping `GET /health` backward compatible; verify tests distinguish API health from actionable processing dependency readiness.

## 2. Canonical Domain and Local Persistence

- [x] 2.1 Define typed domain models for source types, Whisper profiles, transcript/word segments, translated segments, summaries, job errors, and artifact manifest entries; verify model tests reject invalid language codes, empty text, duplicate IDs, and invalid time ranges.
- [x] 2.2 Implement millisecond-based timestamp validation and display/SRT formatting utilities; verify boundary tests cover zero, sub-second values, hour transitions, long durations, and invalid negative or reversed intervals.
- [x] 2.3 Implement the explicit job transition graph and monotonic stage-progress mapping; verify tests cover valid MP3/MP4 and YouTube paths plus every invalid, backward, and post-terminal transition.
- [x] 2.4 Add a SQLite `JobRepository` schema and repository implementation for jobs, safe errors, progress, source metadata, and artifact metadata; verify repository tests cover create/read/update atomicity and persistence across new connections.
- [x] 2.5 Implement application-startup recovery that marks persisted non-terminal jobs failed and preserves completed jobs whose artifacts exist; verify restart tests cover interrupted, completed, and missing-artifact records.
- [x] 2.6 Implement a managed job-directory service using generated identifiers, path containment checks, atomic file replacement, and terminal cleanup rules; verify hostile filenames, traversal attempts, partial writes, and out-of-root cleanup targets cannot escape `runtime/data/jobs`.

## 3. Safe Media Intake and Preparation

- [x] 3.1 Implement strict YouTube URL parsing for supported HTTP(S) watch and short URLs and reject playlists, credentials, arbitrary hosts, articles, and malformed values; verify table-driven URL tests cover accepted and rejected forms.
- [x] 3.2 Implement bounded streaming of MP3/MP4 uploads to generated intake paths with exactly-one-source enforcement; verify API/service tests cover empty, multiple, oversized, misleading MIME, hostile filename, and interrupted uploads.
- [x] 3.3 Implement an ffprobe-backed media inspector using argument arrays, JSON parsing, timeouts, and output limits; verify adapter tests cover valid MP3/MP4 fixtures, corrupt media, missing executable, timeout, and sanitized errors.
- [x] 3.4 Implement an ffmpeg-backed audio extractor/normalizer with deterministic output settings and no shell interpolation; verify fixture tests cover MP3 pass-through/conversion, MP4 extraction, missing audio, subprocess failure, and cleanup.
- [x] 3.5 Implement the yt-dlp Python adapter with single-video and no-playlist constraints, safe managed output paths, and mapped inaccessible/network errors; verify tests use a fake yt-dlp boundary for public, private, removed, playlist, timeout, and output-path cases.
- [x] 3.6 Implement bounded audio chunk planning and overlap-aware merge utilities; verify synthetic tests prove chunk-relative Whisper results become monotonic original-media timestamps without duplicated overlap text.

## 4. Local AI Provider Adapters

- [x] 4.1 Define separate speech-to-text, translation, and summary provider protocols plus dependency-injected factories that expose only Local Whisper and Ollama-compatible implementations; verify contract tests can replace each capability independently with a fake.
- [x] 4.2 Implement the faster-whisper adapter with CPU-safe defaults, word timestamps, explicit English transcription, and `Fast = base.en`, `Balanced = small.en`, `Accurate = medium.en` settings; verify adapter tests cover profile mapping, normalized segment output, progress callbacks, missing models, and sanitized runtime failures.
- [x] 4.3 Implement bounded/chunked Local Whisper orchestration and canonical segment merging; verify tests cover one chunk, multiple chunks, silence, reversed provider timestamps, stable segment IDs, and long-media offset integrity.
- [x] 4.4 Implement the Ollama-compatible HTTP client with configured endpoint/model, finite timeouts, response-size limits, non-streaming structured responses, and safe error mapping; verify mock-server tests cover success, unreachable endpoint, timeout, invalid JSON, oversized response, and model-not-found behavior.
- [x] 4.5 Implement Traditional Chinese translation batching with segment IDs, structured schema validation, one bounded repair retry, and exact one-to-one alignment; verify tests reject missing, duplicate, reordered, empty, or extra translated segments and prove timestamps never change.
- [x] 4.6 Implement English and Traditional Chinese summary providers with bounded map-reduce handling for long transcripts; verify tests cover short and multi-batch transcripts, empty output, provider failure, correct language labels, and absence of Phase 2 chapter/timestamp-citation claims.

## 5. Deterministic Outputs and Downloads

- [x] 5.1 Implement English and Traditional Chinese timestamped transcript renderers with stable UTF-8 and newline rules; verify golden-file tests preserve source ordering, matching bilingual timestamps, punctuation, and non-ASCII text.
- [x] 5.2 Implement deterministic subtitle cue construction using sentence/punctuation boundaries, optional word timings, reading constraints, and original timestamps; verify unit tests cover cue merging/splitting, no-word-timing fallback, long lines, chronological intervals, and repeatable output.
- [x] 5.3 Implement English, Traditional Chinese, and bilingual SRT renderers with sequential indices and `HH:MM:SS,mmm` timecodes; verify golden files are byte-identical across repeated runs and bilingual cues share one timestamp interval.
- [x] 5.4 Implement separate UTF-8 English and Traditional Chinese Markdown summary artifacts and verify tests assert non-empty language-labeled files without chapter, key-point, or timestamp-citation metadata.
- [x] 5.5 Implement versioned canonical `result.json` and the seven-entry artifact manifest, publishing entries only after atomic writes complete; verify tests prevent `COMPLETED` when any required artifact is absent, partial, duplicated, or invalid.
- [x] 5.6 Implement artifact-key lookup and safe streaming metadata for individual downloads; verify tests cover descriptive sanitized filenames, content types, unknown keys, missing files, cross-job access, range/path injection attempts, and absence of absolute paths.

## 6. Pipeline, Worker, and Error Handling

- [x] 6.1 Implement the pipeline orchestrator for acquisition, extraction, transcription, translation, subtitle generation, summary generation, manifest publication, and terminal cleanup; verify fake-backed tests assert exact stage order for YouTube, MP3, and MP4 jobs.
- [x] 6.2 Implement the bounded single-worker in-process queue and FastAPI lifespan startup/shutdown integration without blocking the request event loop; verify concurrency tests show a second job remains `PENDING`, health/status remain responsive, and shutdown does not start new work.
- [x] 6.3 Persist every lifecycle/progress change and clamp overall progress to monotonic 0–100 ranges; verify polling tests observe applicable completed stages, skip `DOWNLOADING` for uploads, and report 100 only after a valid manifest exists.
- [x] 6.4 Add stable error categories and safe user messages for intake, media, Whisper, Ollama, artifact, interruption, and unexpected failures; verify tests prove HTTP responses omit stack traces, subprocess arguments, prompts, credentials, and filesystem paths.
- [x] 6.5 Add structured local logs containing job ID, stage, provider, duration, and sanitized error category; verify log-capture tests redact URL credentials, tokens, prompts, internal paths, and raw provider responses.

## 7. FastAPI Job API

- [x] 7.1 Add versioned request/response schemas and `POST /api/jobs` multipart handling for exactly one source plus local model options; verify API tests cover HTTP 202 creation and all media-intake validation errors.
- [x] 7.2 Add `GET /api/jobs/{job_id}` with stage label, bounded progress, completed-stage data, safe failure details, and terminal result manifest; verify tests cover pending, every active stage, failed, completed, and unknown jobs without leaking internal metadata.
- [x] 7.3 Add `GET /api/jobs/{job_id}/artifacts/{artifact_key}` using server-controlled manifest resolution; verify API tests cover successful streaming, download headers, unknown job/key, missing file, and traversal attempts.
- [x] 7.4 Update CORS methods/headers only as required by the Phase 1 browser API while retaining the explicit allowlist; verify configured origins can submit/poll/download and unconfigured origins receive no browser access grant.
- [x] 7.5 Add a full fake-backed FastAPI integration test from YouTube/upload submission through progress and all seven downloads; verify it runs deterministically without network, FFmpeg, Whisper models, or Ollama.

## 8. Phase 1 Local Web UI

- [x] 8.1 Define typed frontend API contracts and a client for job submission, polling, results, and downloads; verify client tests cover multipart construction, response validation, retryable polling errors, safe terminal errors, and API base URL handling.
- [x] 8.2 Replace the Phase 0-only page with an accessible mutually exclusive YouTube/MP3/MP4 form, Local Whisper profile controls, and visible Ollama configuration summary; verify component tests cover source switching, stale-field clearing, validation, file constraints, and submission payloads.
- [x] 8.3 Implement the `editing` and `submitting` workflow states while retaining backend connectivity guidance and duplicate-submit prevention; verify tests show invalid or offline forms do not submit and accepted jobs transition once to processing.
- [x] 8.4 Implement capped-backoff status polling and the processing view with stage labels, completed stages, and monotonic progress; verify fake-timer tests cover all stages, upload-stage skipping, transient polling failures, recovery, and polling termination.
- [x] 8.5 Implement failed-job recovery that shows safe stage-specific guidance and returns to an editable form only through an intentional action; verify tests prove a retry creates a new job and raw backend diagnostic fields never render.
- [x] 8.6 Implement completed result views for both transcripts, three SRT variants, two summaries, and seven individual download actions; verify component tests cover manifest rendering, language labels, long content, download URLs, and missing-manifest defense.
- [x] 8.7 Update responsive styling and semantic/focus behavior for the full workflow; verify automated accessibility assertions plus desktop and 375×812 tests show keyboard-operable controls and no horizontal overflow.
- [x] 8.8 Replace the Phase 0 Playwright smoke path with fixture-backed Phase 1 success, failure, reconnect, and download scenarios while retaining health connectivity coverage; verify `npm run smoke` passes in installed Google Chrome without live AI or YouTube.

## 9. Documentation, Verification, and Phase Evidence

- [ ] 9.1 Extend development/startup scripts to create managed directories safely, run SQLite initialization, and diagnose FFmpeg/ffprobe, Whisper model, and Ollama readiness; verify clean start, Ctrl+C cleanup, missing-dependency messages, and preservation of completed artifacts on Windows.
- [x] 9.2 Expand `scripts/verify.ps1` with Phase 1 backend, frontend, fixture-media, security, artifact, and browser checks while retaining every Phase 0 gate; verify an induced failure in each major section propagates a non-zero child exit code.
- [x] 9.3 Update README, architecture text, prerequisites, setup/model preparation, configuration table, supported inputs, seven outputs, storage/cleanup, troubleshooting, security, testing, and roadmap truthfulness; verify a clean Windows setup can follow the documented commands and no Phase 2/SaaS feature is claimed complete.
- [ ] 9.4 Add a documented real-local acceptance procedure and small licensed/generated MP3 and MP4 fixtures; verify it records exact tool/model versions and exercises real FFmpeg, one representative Local Whisper transcription, Ollama translation/summary, progress, all seven downloads, safe failures, and restart persistence.
- [x] 9.5 Run the complete deterministic verification gate and fix all regressions; verify backend format/lint/mypy/tests, frontend format/lint/typecheck/tests/build, Playwright, secret scans, and Phase 0 regressions all exit zero in one recorded run.
- [ ] 9.6 Run Windows acceptance for one accessible public YouTube URL, one MP3, and one MP4 without a paid API; verify each reaches `COMPLETED`, preserves timestamps, exposes progress, and downloads all seven readable artifacts.
- [x] 9.7 Create `docs/phase-1-report.md` only from observed verification evidence using the required phase/status/implemented/tests/known-issues/files/run/acceptance format; verify every criterion is marked PASS with evidence or the phase remains explicitly incomplete.
- [x] 9.8 Run `openspec validate establish-phase-1-local-web-ui-mvp --strict` and review the final diff for scope; verify validation passes and no cloud adapter, Phase 2 URL source, RAG, authentication, billing, distributed queue, or SaaS implementation entered the change.
