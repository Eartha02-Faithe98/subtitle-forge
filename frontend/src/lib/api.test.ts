import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  artifactDownloadUrl,
  getJobStatus,
  getLocalConfig,
  submitJob,
} from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Phase 1 API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("constructs a YouTube multipart request without overriding its boundary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          api_version: "1",
          job_id: "00000000-0000-0000-0000-000000000001",
          status_url: "/api/jobs/00000000-0000-0000-0000-000000000001",
        },
        202,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await submitJob(
      {
        sourceType: "youtube",
        youtubeUrl: "https://youtu.be/dQw4w9WgXcQ",
        whisperProfile: "balanced",
      },
      "http://localhost:8100/",
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8100/api/jobs");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ Accept: "application/json" });
    const body = init.body as FormData;
    expect(body.get("source_type")).toBe("youtube");
    expect(body.get("youtube_url")).toBe("https://youtu.be/dQw4w9WgXcQ");
    expect(body.get("whisper_profile")).toBe("balanced");
    expect(body.get("upload")).toBeNull();
  });

  it("constructs an upload multipart request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          api_version: "1",
          job_id: "00000000-0000-0000-0000-000000000001",
          status_url: "/api/jobs/00000000-0000-0000-0000-000000000001",
        },
        202,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["audio"], "sample.mp3", { type: "audio/mpeg" });

    await submitJob(
      { sourceType: "mp3", file, whisperProfile: "fast" },
      "http://localhost:8100",
    );

    const body = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    expect(body.get("source_type")).toBe("mp3");
    expect(body.get("upload")).toBe(file);
    expect(body.get("youtube_url")).toBeNull();
  });

  it("rejects a malformed success response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ job_id: 42 })),
    );

    await expect(
      getJobStatus("00000000-0000-0000-0000-000000000001"),
    ).rejects.toMatchObject({ safeMessage: "後端回應格式無效。" });
  });

  it("marks transient polling failures as retryable without exposing raw details", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: "D:\\private\\prompt API_KEY=secret" }, 503),
        ),
    );

    const error = await getJobStatus(
      "00000000-0000-0000-0000-000000000001",
    ).catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      retryable: true,
      safeMessage: "暫時無法連線到本機後端。",
    });
    expect(String(error)).not.toMatch(/private|API_KEY|secret/);
  });

  it("uses a safe backend validation message for a terminal submission error", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(jsonResponse({ detail: "請選擇有效的來源。" }, 422)),
    );

    await expect(
      submitJob({
        sourceType: "youtube",
        youtubeUrl: "bad",
        whisperProfile: "balanced",
      }),
    ).rejects.toMatchObject({
      retryable: false,
      safeMessage: "請選擇有效的來源。",
    });
  });

  it("builds encoded artifact download URLs from the configured API origin", () => {
    expect(
      artifactDownloadUrl(
        "00000000-0000-0000-0000-000000000001",
        "english transcript",
        "http://localhost:8100/",
      ),
    ).toBe(
      "http://localhost:8100/api/jobs/00000000-0000-0000-0000-000000000001/artifacts/english%20transcript",
    );
  });

  it("validates safe local provider configuration", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          api_version: "1",
          speech_provider: "Local Whisper",
          translation_provider: "Ollama-compatible",
          summary_provider: "Ollama-compatible",
          ollama_model: "qwen2.5:7b",
        }),
      ),
    );

    await expect(getLocalConfig()).resolves.toMatchObject({
      speech_provider: "Local Whisper",
      ollama_model: "qwen2.5:7b",
    });
  });
});
