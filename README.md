# Subtitle Forge

Subtitle Forge is an open-source **AI bilingual media knowledge tool**. Its long-term goal is to turn video and audio into bilingual, timestamp-aware subtitles, transcripts, summaries, and searchable knowledge with evidence linked to the original media.

> Turn any video or audio into bilingual subtitles and knowledge.

## Current status: Phase 1 Local Web UI MVP

The repository provides a tested, local-only media workflow:

- Mutually exclusive public YouTube, MP3, and MP4 inputs.
- FFmpeg media inspection and normalized audio extraction.
- English transcription with Local faster-whisper (`base.en`, `small.en`, or `medium.en`).
- Traditional Chinese translation plus English and Traditional Chinese summaries through a local Ollama-compatible endpoint.
- Timestamped English/Traditional Chinese transcripts; English, Traditional Chinese, and bilingual SRT; and two Markdown summaries.
- A persisted SQLite job queue with monotonic progress, safe failures, restart recovery, and seven individual downloads.
- Responsive Next.js UI, FastAPI API, deterministic tests, and Windows PowerShell startup/verification scripts.

Phase 2 media sources and all knowledge/RAG, authentication, billing, distributed queue, cloud-provider, and SaaS capabilities remain roadmap items and are not implemented.

## Product direction

Subtitle Forge is designed around four priorities:

1. Preserve timestamps as first-class data.
2. Prefer local, open-source AI so a paid API is never mandatory.
3. Keep speech-to-text, translation, and summary capabilities behind independent interfaces.
4. Share core business logic between the initial local application and a possible future SaaS deployment.

Phase 1 deliberately exposes only Local Whisper and an Ollama-compatible local model. No credential-bearing cloud adapter is included.

## Development setup

### Prerequisites

- Windows 11
- Git
- Python 3.11 or newer
- Node.js 20.9 or newer with npm
- FFmpeg with both `ffmpeg` and `ffprobe` on `PATH`
- Local faster-whisper model files for the selected profile
- A running Ollama-compatible service with the configured model
- Google Chrome for the Playwright smoke test

### 1. Create the backend environment

From the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade "pip>=26.2.1"
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
```

### 2. Install frontend dependencies

```powershell
Push-Location frontend
npm install
Pop-Location
```

The committed `package-lock.json` keeps frontend dependency resolution repeatable.

### 3. Prepare local processing dependencies

Confirm FFmpeg:

```powershell
ffmpeg -version
ffprobe -version
```

Download at least the default balanced Whisper model once while online. Processing itself uses local files only:

```powershell
backend\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"
```

Prepare and start the default Ollama model in a separate terminal:

```powershell
ollama pull qwen2.5:7b
ollama serve
```

You may select `base.en` (fast), `small.en` (balanced), or `medium.en` (accurate) in the UI after its local files are prepared.

### 4. Configure local overrides

The defaults work on localhost without an API key. To customize them:

```powershell
Copy-Item .env.example .env
```

`.env` is ignored by Git. Never place real credentials in `.env.example`.

| Variable | Default | Runtime | Purpose |
| --- | --- | --- | --- |
| `SUBTITLE_FORGE_HOST` | `127.0.0.1` | Backend | Local API bind host |
| `SUBTITLE_FORGE_PORT` | `8000` | Backend | Local API port |
| `SUBTITLE_FORGE_ENVIRONMENT` | `development` | Backend | `development`, `test`, or `production` |
| `SUBTITLE_FORGE_ALLOWED_ORIGINS` | localhost ports 3000 | Backend | JSON array of explicit browser origins |
| `SUBTITLE_FORGE_DATA_ROOT` | `runtime/data/jobs` | Backend | Managed per-job source and artifact root |
| `SUBTITLE_FORGE_UPLOAD_MAX_BYTES` | `1073741824` | Backend | Maximum streamed MP3/MP4 upload size |
| `SUBTITLE_FORGE_FFPROBE_TIMEOUT_SECONDS` | `30` | Backend | Media inspection timeout |
| `SUBTITLE_FORGE_FFMPEG_TIMEOUT_SECONDS` | `600` | Backend | Audio preparation/chunk timeout |
| `SUBTITLE_FORGE_YOUTUBE_TIMEOUT_SECONDS` | `900` | Backend | yt-dlp network timeout |
| `SUBTITLE_FORGE_WHISPER_MODELS` | fast/base.en, balanced/small.en, accurate/medium.en | Backend | JSON profile-to-local-model map |
| `SUBTITLE_FORGE_WHISPER_DEVICE` | `cpu` | Backend | `cpu`, `cuda`, or `auto` |
| `SUBTITLE_FORGE_WHISPER_COMPUTE_TYPE` | `int8` | Backend | faster-whisper compute type |
| `SUBTITLE_FORGE_AUDIO_CHUNK_SECONDS` | `900` | Backend | Maximum transcription chunk duration |
| `SUBTITLE_FORGE_AUDIO_CHUNK_OVERLAP_SECONDS` | `5` | Backend | Timestamp-preserving chunk overlap |
| `SUBTITLE_FORGE_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Backend | Local Ollama-compatible origin |
| `SUBTITLE_FORGE_OLLAMA_MODEL` | `qwen2.5:7b` | Backend | Local translation/summary model |
| `SUBTITLE_FORGE_OLLAMA_TIMEOUT_SECONDS` | `180` | Backend | Local generation timeout |
| `SUBTITLE_FORGE_PROMPT_MAX_CHARS` | `12000` | Backend | Bounded local prompt size |
| `SUBTITLE_FORGE_POLL_INTERVAL_MS` | `1000` | Backend | Polling metadata/default |
| `SUBTITLE_FORGE_RETENTION_HOURS` | `168` | Backend | Configured retention metadata |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Browser | Public, non-secret backend origin |
| `FRONTEND_PORT` | `3000` | Startup script | Local Next.js port |

Only `NEXT_PUBLIC_*` values are delivered to browser JavaScript, so they must never contain secrets.

## Run locally

Start both components from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

Then open <http://127.0.0.1:3000>. The script reports `GET /readiness` results for FFmpeg, ffprobe, the default Whisper model, and Ollama. The page enables submission after `GET http://127.0.0.1:8000/health` returns:

```json
{"status":"ok"}
```

Press `Ctrl+C` in the development terminal to stop only the frontend and backend processes launched by the script. Startup logs are written to the ignored `runtime/` directory.

### Supported workflow

Choose exactly one input:

- One public, single-video `youtube.com/watch` or `youtu.be` URL (playlists, credentials, arbitrary hosts, private/removed videos are rejected).
- One MP3 file.
- One MP4 file containing a readable audio stream.

Then choose a Local Whisper mode and submit. One in-process worker handles jobs sequentially; a second accepted job stays pending. Polling continues through download (YouTube only), audio preparation, transcription, Traditional Chinese translation, subtitle generation, and summary generation.

A completed job exposes exactly seven UTF-8 downloads:

1. `transcript-en.txt`
2. `transcript-zh-TW.txt`
3. `subtitles-en.srt`
4. `subtitles-zh-TW.srt`
5. `subtitles-bilingual.srt`
6. `summary-en.md`
7. `summary-zh-TW.md`

Job state is stored in `runtime/data/jobs.sqlite3`; managed sources, temporary audio, `result.json`, and completed artifacts live below `runtime/data/jobs/<job-id>/`. Terminal cleanup removes disposable source/audio files while preserving completed artifacts. Do not place unrelated files in this managed directory.

You can also run the components independently:

```powershell
# Terminal 1, repository root
backend\.venv\Scripts\python.exe -m uvicorn subtitle_forge_api.app:app --host 127.0.0.1 --port 8000

# Terminal 2
Push-Location frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Test and verify

Run the complete deterministic Phase 1 gate from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Individual checks are also available:

```powershell
# Backend
Push-Location backend
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\ruff.exe check .
.venv\Scripts\mypy.exe
.venv\Scripts\python.exe -m pytest -q
Pop-Location

# Frontend
Push-Location frontend
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run smoke
Pop-Location
```

The gate retains every Phase 0 check and adds Phase 1 media/security/artifact/API coverage, production build, strict OpenSpec validation, and fixture-backed browser tests. The smoke test starts real local FastAPI and Next.js servers, opens installed Google Chrome at desktop and 375×812 viewports, and verifies health, keyboard operation, success, safe failure, reconnect, downloads, and horizontal overflow without live AI or YouTube.

## Architecture

```text
Browser
  └─ Next.js Phase 1 workflow
       ├─ POST /api/jobs (YouTube URL or streamed MP3/MP4)
       ├─ GET /api/jobs/{id} (persisted progress/result)
       └─ GET /api/jobs/{id}/artifacts/{key}
            └─ FastAPI + one local worker
                 ├─ yt-dlp / FFmpeg / ffprobe
                 ├─ Local faster-whisper
                 ├─ Ollama-compatible translation and summaries
                 └─ SQLite + managed local artifacts
```

Provider capabilities are separated behind local speech-to-text, translation, and summary interfaces. The Phase 1 runtime intentionally has one in-process worker and no distributed infrastructure.

## Security baseline

- Real environment files, virtual environments, dependencies, builds, logs, caches, browser traces, and temporary runtime data are ignored.
- The backend accepts browser access only from configured origins; wildcard CORS is rejected.
- Invalid configuration stops startup with validation errors.
- The frontend receives only a public API origin and never renders backend exceptions or local filesystem paths.
- Uploads are streamed with a size bound into generated, contained job paths; original filenames never control storage paths.
- YouTube is restricted to public single-video URLs; subprocesses use argument arrays without shell interpolation.
- Downloads resolve server-controlled manifest keys and reject range/path traversal attempts.
- Operational logs contain only job/stage/provider/duration/sanitized category—not URLs, prompts, provider bodies, credentials, or internal paths.
- No API credentials are required or persisted by Phase 1.

## Troubleshooting

- **`/health` works but processing is disabled or fails:** open <http://127.0.0.1:8000/readiness> or read the startup diagnostic. Install missing FFmpeg tools, prepare the selected Whisper model, or start Ollama.
- **Whisper model unavailable:** prepare the exact model mapped to the selected fast/balanced/accurate profile. Runtime transcription uses `local_files_only=True`.
- **Ollama unavailable/model not found:** verify `SUBTITLE_FORGE_OLLAMA_BASE_URL`, run `ollama list`, pull `SUBTITLE_FORGE_OLLAMA_MODEL`, and start the service.
- **Media rejected:** confirm the file extension matches MP3/MP4, the content is valid, and an audio stream is present. Renaming another format is not supported.
- **YouTube rejected:** use a public single-video watch/short URL. Playlists, private/removed videos, and non-YouTube URLs are rejected.
- **Interrupted after restart:** non-terminal persisted jobs are safely marked failed; create a new job. Previously completed artifacts are preserved.
- **Port conflict:** set `SUBTITLE_FORGE_PORT` and `FRONTEND_PORT`; update allowed origins/API origin consistently.

## Roadmap

- **Phase 0 — Foundation (complete):** local UI/API shell, configuration, tests, documentation.
- **Phase 1 — Local Web UI MVP (implemented; real-local acceptance tracked in the Phase 1 report):** YouTube, MP3, MP4, Local Whisper, Traditional Chinese translation, summaries, English/Chinese/bilingual SRT, downloads, and processing progress.
- **Phase 2 — More media sources:** article and website-video URLs.
- **Phase 3 — Knowledge layer:** projects, chapters, key points, and transcript search.
- **Phase 4 — RAG and timestamp-cited Q&A.**
- **Later — Web application and production SaaS architecture.**

Entries after Phase 1 are plans, not claims of available functionality.

## Project documents

- [Development specification](CODEX_DEVELOPMENT_SPEC.md)
- [Contributing guide](CONTRIBUTING.md)
- [MIT License](LICENSE)
- [OpenSpec changes](openspec/changes/)

## License

Subtitle Forge is available under the [MIT License](LICENSE).
