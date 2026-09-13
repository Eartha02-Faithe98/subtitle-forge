# Phase 1 Real-Local Acceptance Procedure

Use this Windows procedure only after the deterministic gate passes. Record observed output; do not infer a PASS from unit or fixture-backed tests.

## 1. Record the environment

```powershell
Get-Date -Format o
python --version
node --version
npm --version
ffmpeg -version | Select-Object -First 1
ffprobe -version | Select-Object -First 1
ollama --version
backend\.venv\Scripts\python.exe -c "import faster_whisper; print(faster_whisper.__version__)"
ollama list
```

Record the exact Whisper profile/model and Ollama model. Do not record credentials or private paths.

## 2. Generate licensed fixtures

`spoken-english.mp3` and `spoken-english.mp4` are generated from Windows text-to-speech; they contain no third-party media.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate-fixtures.ps1
ffprobe -v error -show_entries format=format_name,duration -show_streams -of json .\backend\tests\fixtures\media\spoken-english.mp3
ffprobe -v error -show_entries format=format_name,duration -show_streams -of json .\backend\tests\fixtures\media\spoken-english.mp4
```

## 3. Start and confirm readiness

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

Open <http://127.0.0.1:8000/readiness>. All four dependencies must report `available: true`. Open <http://127.0.0.1:3000> and confirm submission is enabled.

## 4. Exercise real processing

Run three separate jobs:

1. An accessible public, single-video YouTube URL with clear English speech.
2. `backend/tests/fixtures/media/spoken-english.mp3`.
3. `backend/tests/fixtures/media/spoken-english.mp4`.

For each job, record:

- the source type and selected Whisper profile;
- every observed progress stage and monotonic percentage;
- terminal status `COMPLETED`;
- English and Traditional Chinese timestamps remaining aligned and chronological;
- successful, readable downloads for both transcripts, three SRT files, and two summaries;
- no paid API or API key used.

## 5. Safe failure and restart persistence

1. Submit an invalid/non-media upload and record the safe HTTP/UI message. Confirm it contains no stack, command, prompt, credential, or absolute path.
2. Complete a fixture job, note its seven artifact filenames, stop both processes with Ctrl+C, and restart.
3. Confirm the completed job artifacts remain readable below the managed job directory.
4. Interrupt a separate active job, restart, and confirm it is marked failed with the safe interruption category rather than resumed.

## 6. Acceptance rule

Copy only observed commands/results into `docs/phase-1-report.md`. Mark a criterion PASS only when the corresponding real command or UI action succeeded. If FFmpeg, a prepared Whisper model, Ollama, a public YouTube source, or any expected artifact is unavailable, keep Phase 1 acceptance explicitly incomplete.
