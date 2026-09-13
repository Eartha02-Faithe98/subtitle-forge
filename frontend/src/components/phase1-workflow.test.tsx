import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { JobCreated, JobStatus, Phase1Result } from "@/lib/api";

import { Phase1Workflow, type WorkflowApi } from "./phase1-workflow";

const jobId = "00000000-0000-0000-0000-000000000001";

function created(id = jobId): JobCreated {
  return { api_version: "1", job_id: id, status_url: `/api/jobs/${id}` };
}

function status(stage: JobStatus["stage"], progress: number): JobStatus {
  return {
    api_version: "1",
    job_id: jobId,
    stage,
    stage_label:
      stage === "TRANSCRIBING" ? "Transcribing with Local Whisper" : stage,
    progress,
    completed_stages: stage === "PENDING" ? [] : ["EXTRACTING_AUDIO"],
    error: null,
    result: null,
  };
}

function result(): Phase1Result {
  const artifacts: Phase1Result["artifacts"] = [
    "english_transcript",
    "traditional_chinese_transcript",
    "english_srt",
    "traditional_chinese_srt",
    "bilingual_srt",
    "english_summary",
    "traditional_chinese_summary",
  ].map((kind, index) => ({
    artifact_key: kind,
    kind: kind as Phase1Result["artifacts"][number]["kind"],
    filename: `${kind}.${kind.includes("srt") ? "srt" : "txt"}`,
    media_type: "text/plain; charset=utf-8",
    size_bytes: 100 + index,
  }));
  return {
    schema_version: "1.0",
    job_id: jobId,
    transcript: {
      language: "en",
      segments: [
        {
          segment_id: "s1",
          start_ms: 0,
          end_ms: 1_000,
          source_text: "Hello world.",
        },
      ],
    },
    translated: {
      language: "zh-TW",
      segments: [
        {
          segment_id: "s1",
          start_ms: 0,
          end_ms: 1_000,
          translated_text: "哈囉，世界。",
        },
      ],
    },
    summaries: [
      { language: "en", text: "English summary" },
      { language: "zh-TW", text: "繁體中文摘要" },
    ],
    artifacts,
  };
}

function fakeApi(overrides: Partial<WorkflowApi> = {}): WorkflowApi {
  return {
    checkHealth: vi.fn().mockResolvedValue(true),
    getLocalConfig: vi.fn().mockResolvedValue({
      api_version: "1",
      speech_provider: "Local Whisper",
      translation_provider: "Ollama-compatible",
      summary_provider: "Ollama-compatible",
      ollama_model: "qwen2.5:7b",
    }),
    submitJob: vi.fn().mockResolvedValue(created()),
    getJobStatus: vi.fn().mockResolvedValue(status("PENDING", 0)),
    artifactDownloadUrl: vi.fn(
      (id, key) => `http://api/jobs/${id}/artifacts/${key}`,
    ),
    ...overrides,
  };
}

describe("Phase1Workflow", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps YouTube, MP3, and MP4 mutually exclusive and clears stale source values", async () => {
    const api = fakeApi();
    render(<Phase1Workflow api={api} />);
    await screen.findByText("本機後端已連線");
    expect(await screen.findByText(/qwen2\.5:7b/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("YouTube 網址"), {
      target: { value: "https://youtu.be/dQw4w9WgXcQ" },
    });
    fireEvent.click(screen.getByLabelText("MP3 檔案"));

    expect(screen.queryByLabelText("YouTube 網址")).not.toBeInTheDocument();
    const file = new File(["audio"], "sample.mp3", { type: "audio/mpeg" });
    fireEvent.change(screen.getByLabelText("選擇 MP3 檔案"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByLabelText("YouTube 網址來源"));
    fireEvent.click(screen.getByLabelText("MP3 檔案"));

    expect(
      screen.getByLabelText<HTMLInputElement>("選擇 MP3 檔案").files,
    ).toHaveLength(0);
  });

  it("validates source input and submits exactly once with the selected profile", async () => {
    let resolveSubmission: (value: JobCreated) => void = () => undefined;
    const api = fakeApi({
      submitJob: vi.fn(
        () =>
          new Promise<JobCreated>((resolve) => (resolveSubmission = resolve)),
      ),
    });
    render(<Phase1Workflow api={api} />);
    await screen.findByText("本機後端已連線");

    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "請輸入有效的 YouTube 網址",
    );
    fireEvent.change(screen.getByLabelText("YouTube 網址"), {
      target: { value: "https://youtu.be/dQw4w9WgXcQ" },
    });
    fireEvent.click(screen.getByLabelText(/快速/));
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));
    fireEvent.click(screen.getByRole("button", { name: "正在建立工作…" }));

    expect(api.submitJob).toHaveBeenCalledTimes(1);
    expect(api.submitJob).toHaveBeenCalledWith({
      sourceType: "youtube",
      youtubeUrl: "https://youtu.be/dQw4w9WgXcQ",
      whisperProfile: "fast",
    });
    await act(async () => resolveSubmission(created()));
    expect(
      await screen.findByRole("heading", { name: "處理進度" }),
    ).toBeInTheDocument();
  });

  it("rejects an empty or mismatched local media file before submission", async () => {
    const api = fakeApi();
    render(<Phase1Workflow api={api} />);
    await screen.findByText("本機後端已連線");
    fireEvent.click(screen.getByLabelText("MP4 檔案"));
    fireEvent.change(screen.getByLabelText("選擇 MP4 檔案"), {
      target: {
        files: [new File([], "empty.mp4", { type: "video/mp4" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));
    expect(screen.getByRole("alert")).toHaveTextContent("檔案不可為空");

    fireEvent.change(screen.getByLabelText("選擇 MP4 檔案"), {
      target: {
        files: [new File(["media"], "wrong.mp3", { type: "audio/mpeg" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));
    expect(screen.getByRole("alert")).toHaveTextContent("副檔名必須是 .mp4");
    expect(api.submitJob).not.toHaveBeenCalled();
  });

  it("does not submit while the backend is offline and shows connection guidance", async () => {
    const api = fakeApi({ checkHealth: vi.fn().mockResolvedValue(false) });
    render(<Phase1Workflow api={api} />);

    expect(await screen.findByText("本機後端未連線")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "開始處理" })).toBeDisabled();
    expect(screen.getByText(/請先啟動 FastAPI/)).toBeInTheDocument();
    expect(api.submitJob).not.toHaveBeenCalled();
  });

  it("polls with recovery, preserves monotonic progress, and stops on completion", async () => {
    vi.useFakeTimers();
    const completed = status("COMPLETED", 100);
    completed.result = result();
    const api = fakeApi({
      getJobStatus: vi
        .fn()
        .mockRejectedValueOnce(new Error("offline"))
        .mockResolvedValueOnce(status("TRANSCRIBING", 45))
        .mockResolvedValueOnce(status("TRANSCRIBING", 20))
        .mockResolvedValueOnce(completed),
    });
    render(<Phase1Workflow api={api} pollSchedule={[10, 20, 40]} />);
    await act(async () => vi.runOnlyPendingTimersAsync());
    fireEvent.change(screen.getByLabelText("YouTube 網址"), {
      target: { value: "https://youtu.be/dQw4w9WgXcQ" },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));
    await act(async () => Promise.resolve());

    await act(async () => vi.advanceTimersByTimeAsync(10));
    expect(screen.getByText(/重新連線/)).toBeInTheDocument();
    await act(async () => vi.advanceTimersByTimeAsync(20));
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "45",
    );
    await act(async () => vi.advanceTimersByTimeAsync(10));
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "45",
    );
    await act(async () => vi.advanceTimersByTimeAsync(10));

    expect(
      screen.getByRole("heading", { name: "處理完成" }),
    ).toBeInTheDocument();
    expect(api.getJobStatus).toHaveBeenCalledTimes(4);
  });

  it("shows every applicable stage and skips downloading for uploads", async () => {
    const api = fakeApi();
    render(<Phase1Workflow api={api} pollSchedule={[10_000]} />);
    await screen.findByText("本機後端已連線");
    fireEvent.click(screen.getByLabelText("MP3 檔案"));
    fireEvent.change(screen.getByLabelText("選擇 MP3 檔案"), {
      target: {
        files: [new File(["audio"], "sample.mp3", { type: "audio/mpeg" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));

    expect(
      await screen.findByRole("heading", { name: "處理進度" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("下載 YouTube 媒體")).not.toBeInTheDocument();
    for (const label of [
      "準備音訊",
      "Local Whisper 轉錄",
      "翻譯為繁體中文",
      "產生字幕",
      "產生摘要",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("shows fixed safe failure guidance and requires an intentional new-job action", async () => {
    const failed = status("FAILED", 30);
    failed.error = {
      category: "ollama_unavailable",
      stage: "TRANSLATING",
      message: "D:\\private\\prompt.txt TOKEN=secret raw provider response",
    };
    const api = fakeApi({ getJobStatus: vi.fn().mockResolvedValue(failed) });
    render(<Phase1Workflow api={api} pollSchedule={[1]} />);
    await screen.findByText("本機後端已連線");
    fireEvent.change(screen.getByLabelText("YouTube 網址"), {
      target: { value: "https://youtu.be/dQw4w9WgXcQ" },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));

    expect(
      await screen.findByRole("heading", { name: "處理失敗" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Ollama/)).toBeInTheDocument();
    expect(
      screen.queryByText(/private|TOKEN|provider response/),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "修改設定並建立新工作" }),
    );
    expect(
      screen.getByRole("heading", { name: "建立字幕工作" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));
    await waitFor(() => expect(api.submitJob).toHaveBeenCalledTimes(2));
  });

  it("renders both transcripts, summaries, three SRT downloads, and all seven artifacts", async () => {
    const completed = status("COMPLETED", 100);
    completed.result = result();
    const api = fakeApi({ getJobStatus: vi.fn().mockResolvedValue(completed) });
    render(<Phase1Workflow api={api} pollSchedule={[1]} />);
    await screen.findByText("本機後端已連線");
    fireEvent.change(screen.getByLabelText("YouTube 網址"), {
      target: { value: "https://youtu.be/dQw4w9WgXcQ" },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));

    expect(
      await screen.findByRole("heading", { name: "處理完成" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "英文逐字稿" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Hello world.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "繁體中文逐字稿" }),
    ).toBeInTheDocument();
    expect(screen.getByText("哈囉，世界。")).toBeInTheDocument();
    expect(screen.getByText("English summary")).toBeInTheDocument();
    expect(screen.getAllByText("繁體中文摘要").length).toBeGreaterThanOrEqual(
      2,
    );
    expect(screen.getAllByRole("link", { name: /下載/ })).toHaveLength(7);
    expect(
      screen.getByRole("link", { name: "下載 英文 SRT" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "下載 繁體中文 SRT" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "下載 雙語 SRT" }),
    ).toBeInTheDocument();
  });

  it("defends against a completed response whose manifest is missing", async () => {
    const malformed = status("COMPLETED", 100);
    const api = fakeApi({ getJobStatus: vi.fn().mockResolvedValue(malformed) });
    render(<Phase1Workflow api={api} pollSchedule={[1]} />);
    await screen.findByText("本機後端已連線");
    fireEvent.change(screen.getByLabelText("YouTube 網址"), {
      target: { value: "https://youtu.be/dQw4w9WgXcQ" },
    });
    fireEvent.click(screen.getByRole("button", { name: "開始處理" }));

    expect(
      await screen.findByRole("heading", { name: "處理失敗" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/完整結果尚未就緒/)).toBeInTheDocument();
  });
});
