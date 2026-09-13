## Context

See `proposal.md` for motivation. The repository currently has a deliberately small Next.js 16 frontend, a FastAPI application factory with only `GET /health`, environment-based settings, and a complete Phase 0 verification gate. There are no media, persistence, background-job, provider, artifact, or download modules to preserve.

Phase 1 must run on Windows 11, keep normal use in the browser, preserve timestamps as domain data, work without a paid API, and remain testable without live YouTube or nondeterministic model calls. Processing can take much longer than an HTTP request, media is untrusted, and the target computers may be CPU-only. The design therefore adds explicit local boundaries without adopting distributed infrastructure.

## Goals / Non-Goals

**Goals:**

- Establish one canonical timestamped transcript model used by translation, subtitles, summaries, persistence, and API responses.
- Keep the FastAPI process responsive while one local worker executes CPU-, disk-, network-, and model-intensive jobs.
- Make media acquisition, AI providers, artifact storage, and job persistence independently testable.
- Provide safe local defaults for CPU-only Windows systems and understandable performance profiles.
- Make every completed output reproducible or traceable to a versioned job result manifest.

**Non-Goals:**

- Parallel or distributed workers, durable resume from a partially executed stage, autoscaling, or remote object storage.
- Cloud AI adapters, API-key persistence, provider marketplace behavior, or a general-purpose settings subsystem.
- Editing, synchronizing, burning in, batching, zipping, searching, embedding, or sharing outputs.
- Supporting non-English source speech as an acceptance requirement; Phase 1 optimizes Local Whisper for English input and produces `zh-TW` translation.

## Decisions

### 1. Extend the existing application as a modular monolith

FastAPI remains the single local API and orchestration process. New backend packages will separate `domain`, `media`, `providers`, `pipeline`, `jobs`, `artifacts`, and `api` responsibilities. Next.js remains a browser client of versioned JSON/multipart endpoints.

This keeps startup and debugging simple while making the business modules portable to a future worker. A microservice split was rejected because it would add deployment and failure boundaries without helping a single-user local MVP. Putting the pipeline directly in route functions was rejected because it would block requests and couple HTTP behavior to subprocess and model details.

### 2. Use a canonical, versioned job result model

The domain layer owns immutable value objects for `MediaSource`, `TranscriptSegment`, `TranslatedSegment`, `Summary`, and `ArtifactManifestEntry`. Segment identifiers and original-media start/end milliseconds are canonical; formatted timestamp strings are derived only at presentation or artifact generation time. Translation attaches text to an existing segment identity and cannot replace timing.

Each completed job writes a versioned `result.json` manifest alongside generated files. This is the boundary used by the API and provides a future migration point. Storing only rendered text was rejected because it would discard the timestamped structure needed for deterministic regeneration and later knowledge features.

### 3. Use a SQLite repository plus managed filesystem artifacts

Use Python's SQLite support behind a `JobRepository` interface for job state, stage progress, error metadata, source metadata, timestamps, and artifact manifest metadata. Store media, canonical result JSON, transcripts, summaries, and SRT files under `runtime/data/jobs/<uuid>/`, which is already beneath ignored runtime storage. Use generated UUIDs and server-owned artifact keys for every lookup; retain an original display name only after sanitization.

SQLite provides atomic local state transitions and restart visibility without introducing an ORM or server dependency. Storing all binary media in SQLite was rejected because large blobs complicate cleanup and downloads. Pure in-memory state was rejected because completed downloads and interrupted-job detection would disappear after restart.

On startup, non-terminal persisted jobs become `FAILED` with an interruption category. Phase 1 does not resume mid-stage. A configurable retention policy removes disposable source/audio files after terminal completion and can remove an entire expired job directory only after validating that its resolved path is inside the managed root.

### 4. Run a bounded in-process local job queue

`POST /api/jobs` validates and streams the source into managed intake storage, records `PENDING`, enqueues the job, and returns HTTP 202 with its identifier. A single dedicated worker consumes jobs sequentially so simultaneous model loads do not exhaust typical local machines. Blocking model work and subprocess waits run off the web event loop. The API continues serving status and downloads while the worker runs.

The state transition service is the only writer of lifecycle changes and enforces the transition graph. Stage progress is represented as a stage plus a monotonic overall percentage range; providers may report bounded progress within their assigned range, but the UI never fabricates time remaining.

A general queue product was rejected as SaaS infrastructure. Unbounded `BackgroundTasks` were rejected because they provide weak concurrency control and make lifecycle/restart behavior difficult to test.

### 5. Define a small Phase 1 API

- `POST /api/jobs` accepts multipart form data containing `source_type`, one YouTube URL or one upload, and local model selections; it returns HTTP 202 with `job_id`.
- `GET /api/jobs/{job_id}` returns stage, progress, safe error data, and the result manifest when complete.
- `GET /api/jobs/{job_id}/artifacts/{artifact_key}` streams one server-controlled artifact with download headers.
- `GET /health` remains unchanged.

The client polls the job resource with capped backoff. Polling was chosen over WebSockets or server-sent events because Phase 1 has a single local user, few status updates, and needs robust reconnect behavior more than low latency. The response schema is versioned and never contains absolute paths, subprocess arguments, model prompts, or raw exceptions.

### 6. Isolate media tools behind typed services

`MediaProbe` invokes `ffprobe` with JSON output; `AudioExtractor` invokes `ffmpeg`; and `YouTubeSource` uses the supported yt-dlp Python API with playlist processing disabled. Every external invocation receives an argument list or library options, never a shell-built command. The YouTube adapter accepts only recognized YouTube hosts and verifies the extractor result represents one video. Private/authenticated content and cookie import are outside Phase 1.

Uploads are streamed in bounded chunks while counting bytes, then probed before acceptance. Browser MIME type and filename extensions are hints only. The backend enforces a configurable byte limit, safe generated names, subprocess timeouts, output limits, and cleanup in `finally` paths.

Direct scattered subprocess calls were rejected because they are harder to sanitize, fake, time out, and diagnose consistently.

### 7. Implement Local Whisper with a replaceable adapter

Define a `SpeechToTextProvider` protocol and implement Phase 1 with `faster-whisper`. Default execution is CPU-compatible with an explicit compute configuration; optional hardware acceleration is configuration, not an MVP requirement. Map UI profiles to documented English models initially as `Fast = base.en`, `Balanced = small.en`, and `Accurate = medium.en`, while keeping the mapping in backend settings so it can be adjusted without frontend code changes.

Request word timestamps when available. Canonical transcript segments keep segment-level millisecond timing, while optional word timings allow deterministic, readable subtitle cue splitting without guessing new timestamps. Long audio is handled through bounded chunks with overlap; merge logic converts chunk-relative timing to original-media timing, removes overlap duplicates, and validates chronological order.

The original `openai-whisper` package was considered, but `faster-whisper` offers a focused local adapter, CPU integer computation, and direct segment iteration. Auto-downloading a large default model at job execution time is avoided: startup/readiness and error guidance make the selected model's local availability explicit, and setup documentation explains the one-time model preparation.

### 8. Use Ollama-compatible HTTP providers with structured contracts

Translation and summary have separate protocols even though both initially call one configurable local Ollama-compatible HTTP endpoint and model. Translation sends bounded batches containing segment IDs and source text and requests structured JSON. The adapter validates exact ID coverage, ordering, non-empty `zh-TW` values, and response size before attaching translations. A bounded repair retry is allowed for malformed structure; repeated mismatch fails the job.

Summary uses a map-reduce strategy for transcripts beyond the configured prompt budget: summarize bounded transcript ranges, then synthesize one final English summary; generate the Traditional Chinese summary through a separately labeled provider call. Phase 1 summaries are plain language artifacts and do not claim timestamp citations.

Using the local provider's CLI was rejected because HTTP provides clearer timeouts, structured responses, and test doubles. Treating one generic provider as all three capabilities was rejected because it would prevent independent future replacement.

### 9. Generate artifacts from canonical data

Create UTF-8 transcript text files with `[HH:MM:SS]` segment markers, UTF-8 Markdown summary files, and three deterministic SRT files. A pure subtitle builder operates only on canonical segments and translations. It prefers Whisper sentence/punctuation boundaries; it may merge adjacent short segments and may split a long segment only where word timestamps provide a defensible interval. It enforces cue order, valid intervals, reading constraints, and stable newline/encoding rules.

The bilingual SRT renders English then Traditional Chinese under one cue interval. Translation never causes timestamp regeneration. Every artifact is written to a temporary file in the job directory and atomically renamed before its manifest entry is published, preventing partial downloads.

### 10. Replace the home shell with a client-side workflow state machine

The frontend owns a discriminated workflow state: `editing`, `submitting`, `processing`, `completed`, or `failed`. Source-specific controls are mutually exclusive. The form exposes only Local Whisper and Ollama-compatible local processing, with the three plain-language Whisper profiles. Submission errors remain in the editing state; a returned job identifier moves the UI to processing; status polling drives progress; terminal status renders results or recovery guidance.

Result previews use the canonical API response, while download buttons target manifest URLs. The existing backend health state remains visible and disables job submission when the API is unavailable. Responsive and keyboard-accessible behavior is covered at component and browser levels.

### 11. Separate deterministic verification from manual local acceptance

Unit tests cover transition graphs, URL and upload validation, path containment, timestamps, chunk merging, translation response validation, subtitle golden files, artifact manifests, and configuration. FastAPI integration tests replace media and AI boundaries with fakes and exercise submission through download. Frontend tests cover all workflow states; Playwright runs a fixture-backed end-to-end path at desktop and 375-pixel viewports while preserving the Phase 0 connectivity regression.

The complete automated gate must not require live YouTube, a downloaded Whisper model, or nondeterministic Ollama output. A documented Windows acceptance procedure separately exercises one public YouTube video, one MP3, one MP4, real FFmpeg/ffprobe, each Whisper profile at least for readiness (with one full representative transcription), Ollama translation/summary, all seven downloads, failure messages, and restart persistence. Phase 1 is complete only after both gates pass.

## Risks / Trade-offs

- **[YouTube extraction changes outside the project]** → Pin and document yt-dlp, reject authenticated/private content, expose an actionable acquisition error, and keep the adapter replaceable. Do not add cookie or token management in Phase 1.
- **[Local models are large and slow on CPU-only systems]** → Use one worker, CPU-safe defaults, three documented profiles, bounded chunks, dependency readiness messages, and no time estimate promises.
- **[GPU libraries can be fragile on Windows]** → Make CPU execution the acceptance baseline and treat GPU acceleration as optional configuration with separate documentation and tests where hardware exists.
- **[LLM translation can violate alignment]** → Require structured segment IDs, validate complete one-to-one coverage, bound retries, and fail instead of emitting silently misaligned subtitles.
- **[Polling adds repeated local requests]** → Use a modest interval with capped backoff and stop immediately on terminal status; the local single-user load is negligible.
- **[In-process jobs are lost on process termination]** → Persist every transition, mark interrupted jobs failed on startup, and keep artifacts from completed jobs. Mid-stage resume is deliberately deferred.
- **[Disk use can grow with long videos and multiple artifacts]** → Enforce upload limits, keep all paths under one managed root, delete disposable intermediates, document retention, and make cleanup containment-testable.
- **[Automated fakes can hide real tool incompatibility]** → Maintain a separate real Windows acceptance checklist and record exact tool/model versions and evidence in the Phase 1 report.

## Migration Plan

1. Add configuration and managed-storage defaults without changing the existing startup command or `GET /health`.
2. Add domain models, SQLite schema creation, repositories, state transitions, and startup recovery. Existing installations have no Phase 1 data to migrate.
3. Add media, provider, pipeline, and artifact services behind fakes and complete backend tests before exposing routes.
4. Add job submission, status, and download APIs, then replace the Phase 0 page with the Phase 1 workflow while retaining health and CORS behavior.
5. Expand setup scripts, `.env.example`, ignore assertions, verification gates, README, and Windows acceptance documentation.
6. Run deterministic verification, then real local acceptance for YouTube, MP3, and MP4. Create `docs/phase-1-report.md` only from observed evidence.

Rollback is a code rollback to the Phase 0 application. The ignored `runtime/data` directory can be retained because Phase 0 does not read it; cleanup, if desired, must be an explicit user action against the resolved managed directory rather than an automatic destructive rollback.
