# Local API Origin Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject browser-originated, cross-site job submissions before FastAPI reads uploads, creates local storage, writes SQLite records, or queues processing.

**Architecture:** Add a focused ASGI middleware that intercepts only `POST /api/jobs`. It permits absent `Origin` headers for local CLI compatibility and validates supplied origins against the existing normalized settings allowlist. Add API integration tests that exercise the real middleware stack and prove denial has no managed-storage, database, or queue side effect.

**Tech Stack:** Python 3.11+, FastAPI/Starlette ASGI middleware, Pydantic settings, pytest, httpx ASGITransport.

---

### Task 1: Add red API security tests

**Files:**
- Modify: `backend/tests/test_jobs_api.py`
- Test: `backend/tests/test_jobs_api.py`

- [x] **Step 1: Write failing tests for accepted and rejected browser origins**

Add the following tests after `test_youtube_job_is_created_with_http_202_and_canonical_source`:

```python
@pytest.mark.anyio
async def test_youtube_job_accepts_configured_browser_origin(tmp_path: Path) -> None:
    app, repository, _storage, queue = api(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/jobs",
            headers={"Origin": "http://localhost:3000"},
            data={
                "source_type": "youtube",
                "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                "whisper_profile": "balanced",
            },
        )

    assert response.status_code == 202
    assert len(queue.requests) == 1
    repository.close()


@pytest.mark.anyio
@pytest.mark.parametrize("origin", ["https://untrusted.example", "not an origin"])
async def test_job_creation_rejects_untrusted_origin_before_side_effects(
    tmp_path: Path, origin: str
) -> None:
    app, repository, storage, queue = api(tmp_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/jobs",
            headers={"Origin": origin},
            data={
                "source_type": "youtube",
                "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                "whisper_profile": "balanced",
            },
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "This browser origin is not allowed."}
    assert queue.requests == []
    assert repository.list_by_stages(tuple(JobStage)) == ()
    assert list(storage.root.iterdir()) == []
    repository.close()
```

Add `JobStage` to the existing `subtitle_forge_api.domain` import.

- [x] **Step 2: Run the targeted test to verify it fails**

Run:

```powershell
Set-Location D:\Project\subtitle-forge\backend
.\.venv\Scripts\python.exe -m pytest tests\test_jobs_api.py -q
```

Expected: the configured-origin test passes under the current API, while each
untrusted-origin case fails because it incorrectly receives `202` and causes a
queue/storage side effect.

### Task 2: Implement the pre-body origin guard

**Files:**
- Create: `backend/src/subtitle_forge_api/origin_guard.py`
- Modify: `backend/src/subtitle_forge_api/app.py`
- Test: `backend/tests/test_jobs_api.py`

- [x] **Step 1: Create the minimal ASGI middleware**

Create `backend/src/subtitle_forge_api/origin_guard.py` with a `SubmissionOriginMiddleware` class. Its `__call__` implementation must only branch for HTTP `POST` requests whose `scope["path"]` is `/api/jobs`. It must read `Origin` using `starlette.datastructures.Headers`, accept an absent header, and otherwise call `_is_configured_origin`.

Use this exact validation shape:

```python
def _is_configured_origin(value: str, allowed_origins: frozenset[str]) -> bool:
    try:
        parsed = urlparse(value)
        _port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        return False
    return value.rstrip("/") in allowed_origins
```

For a rejected request, return before awaiting the wrapped app:

```python
await JSONResponse(
    status_code=403,
    content={"detail": "This browser origin is not allowed."},
)(scope, receive, send)
return
```

- [x] **Step 2: Register the middleware in the application factory**

Import `SubmissionOriginMiddleware` in
`backend/src/subtitle_forge_api/app.py`. After constructing the FastAPI
application and before registering routes, add:

```python
application.add_middleware(
    SubmissionOriginMiddleware,
    allowed_origins=resolved_settings.allowed_origins,
)
```

Keep the existing `CORSMiddleware` configuration unchanged. The origin guard
must be the outer request boundary so it rejects a multipart request before
FastAPI parses its body; do not add a route dependency instead.

- [x] **Step 3: Run the targeted test to verify it passes**

Run:

```powershell
Set-Location D:\Project\subtitle-forge\backend
.\.venv\Scripts\python.exe -m pytest tests\test_jobs_api.py -q
```

Expected: all tests pass; both untrusted-origin parametrizations return `403`,
and the configured-origin and origin-less submissions return `202`.

- [x] **Step 4: Run focused static checks**

Run:

```powershell
.\.venv\Scripts\ruff.exe format --check src\subtitle_forge_api\origin_guard.py tests\test_jobs_api.py
.\.venv\Scripts\ruff.exe check src\subtitle_forge_api\origin_guard.py tests\test_jobs_api.py
.\.venv\Scripts\python.exe -m mypy src\subtitle_forge_api
```

Expected: each command exits with code `0`. The repository mypy configuration
checks the production package; pytest files are verified through their test,
format, and lint commands instead of adding unrelated type annotations.

### Task 3: Verify the security change and delivery state

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-local-api-origin-validation-design.md`
- Modify: `docs/superpowers/plans/2026-09-14-local-api-origin-validation.md`
- Verify: `scripts/verify.ps1`

- [x] **Step 1: Check the security boundary directly**

Run the targeted test once more with verbose output:

```powershell
Set-Location D:\Project\subtitle-forge\backend
.\.venv\Scripts\python.exe -m pytest tests\test_jobs_api.py::test_job_creation_rejects_untrusted_origin_before_side_effects -v
```

Expected: two passed cases, covering an unlisted valid origin and a malformed
origin, with no side effects asserted by the test.

- [x] **Step 2: Run the deterministic full verification gate**

Stop any manually started frontend or backend servers first, then run from the
repository root:

```powershell
Set-Location D:\Project\subtitle-forge
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Expected: backend formatting, linting, type checks, and tests; frontend
formatting, linting, type checks, unit tests, production build, browser smoke
tests; and strict OpenSpec validation all complete successfully.

- [x] **Step 3: Re-run dependency and secret scans**

Run:

```powershell
Set-Location D:\Project\subtitle-forge\frontend
npm.cmd audit --omit=dev --json

Set-Location D:\Project\subtitle-forge\backend
.\.venv\Scripts\python.exe -m pip_audit --progress-spinner=off
```

Expected: zero npm production dependency vulnerabilities and no known audited
Python dependency vulnerabilities. Keep `.env`, runtime data, virtual
environments, logs, and generated browser artifacts ignored.

- [ ] **Step 4: Commit all verified Phase 1 and origin-guard changes**

Run from the repository root after reviewing the staged file list:

```powershell
git status --short
git add .env.example README.md backend frontend docs openspec scripts
git diff --cached --check
git commit -m "feat: deliver phase one local media workflow"
```

Expected: no whitespace errors and one commit containing only source, tests,
documentation, OpenSpec artifacts, and scripts; no local runtime data,
credentials, or virtual environments.

- [ ] **Step 5: Push the verified branch**

Run:

```powershell
git push origin main
```

Expected: the current `main` commits, including the design-spec commit and the
verified implementation commit, are accepted by `origin/main`.
