## Why

Phase 0 proved that the local Next.js and FastAPI application can start, communicate, and pass its quality gates, but users still cannot turn media into usable bilingual outputs. Phase 1 should deliver the first complete local-first workflow while keeping timestamps, provider boundaries, security, and testability intact without introducing Phase 2 sources or SaaS infrastructure.

## What Changes

- Replace the Phase 0 informational shell with a Local Web UI workflow for exactly one YouTube URL, MP3 upload, or MP4 upload per job.
- Add validated media intake, YouTube retrieval, FFmpeg probing/audio extraction, safe temporary-file handling, and user-facing failure messages.
- Add explicit local processing jobs with observable stage progress from intake through download-ready completion.
- Add provider/service boundaries and initial local implementations: Local Whisper for English speech-to-text and an Ollama-compatible local provider for Traditional Chinese translation and English/Traditional Chinese summaries.
- Preserve transcript segment timestamps throughout transcription, translation, display, subtitle generation, and persisted job artifacts.
- Generate English and Traditional Chinese timestamped transcripts, English/Traditional Chinese/bilingual SRT files, and English/Traditional Chinese summaries.
- Let users view results and download each generated artifact from the Local Web UI.
- Extend automated verification, documentation, and phase reporting to cover the complete Phase 1 workflow while retaining all Phase 0 regressions.
- Explicitly exclude cloud-provider adapters and credential UI, article or arbitrary website URLs, subtitle editing or burn-in, batch or ZIP export, chapters, key points, search, RAG/Q&A, authentication, billing, distributed queues, and all other Phase 2 or SaaS capabilities.

## Capabilities

### New Capabilities

- `media-intake`: Accept and safely validate one YouTube URL, MP3 upload, or MP4 upload for local processing.
- `local-ai-media-pipeline`: Extract audio and run timestamp-preserving Local Whisper transcription plus Ollama-compatible local translation and summary providers.
- `processing-jobs`: Model the local processing lifecycle, expose progress, and report actionable failures through explicit job states.
- `bilingual-output-artifacts`: Produce, retain, present, and individually download timestamped transcripts, three SRT variants, and two summaries.
- `phase-1-local-web-workflow`: Provide the end-to-end browser workflow for submitting supported media, choosing understandable local options, monitoring progress, reviewing results, and downloading outputs.

### Modified Capabilities

- `local-application-foundation`: Replace the Phase 0-only informational UI requirement with a truthful Phase 1 application shell while retaining local startup, health, connectivity, and constrained CORS behavior.
- `project-quality-baseline`: Extend the verification, documentation, regression, and evidence-based completion requirements from the Phase 0 foundation to the Phase 1 end-to-end MVP.

## Impact

- **Backend:** FastAPI routes and application assembly; new domain models, media, provider, pipeline, job, artifact, persistence, and download modules; configuration; structured logging; and tests.
- **Frontend:** The Next.js home workflow, upload and URL forms, local processing options, progress and error states, result previews, downloads, responsive styling, component tests, and browser smoke coverage.
- **Runtime dependencies:** FFmpeg/ffprobe, a supported local Whisper runtime and model, yt-dlp-compatible YouTube retrieval, and an Ollama-compatible local service/model for translation and summaries; exact libraries and supported versions will be documented and pinned during implementation.
- **Local storage:** SQLite-backed job metadata and filesystem-backed artifacts under an ignored application data directory, with safe names and cleanup rules; no remote database, object storage, or distributed worker.
- **APIs:** Local endpoints for media submission, job status/results, and artifact downloads, while retaining `GET /health` and explicit CORS allowlisting.
- **Compatibility:** No public backward-incompatible API exists yet; Phase 0 startup and health behavior remain supported and tested.
