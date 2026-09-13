"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  ApiError,
  artifactDownloadUrl,
  checkBackendHealth,
  getJobStatus,
  getLocalConfig,
  type JobCreated,
  type JobStage,
  type JobStatus,
  type JobSubmission,
  type LocalProviderConfig,
  type Phase1Result,
  type SourceType,
  submitJob,
  type WhisperProfile,
} from "@/lib/api";

export interface WorkflowApi {
  checkHealth(): Promise<boolean>;
  getLocalConfig(): Promise<LocalProviderConfig>;
  submitJob(submission: JobSubmission): Promise<JobCreated>;
  getJobStatus(jobId: string): Promise<JobStatus>;
  artifactDownloadUrl(jobId: string, artifactKey: string): string;
}

const defaultApi: WorkflowApi = {
  checkHealth: () => checkBackendHealth(),
  getLocalConfig: () => getLocalConfig(),
  submitJob: (submission) => submitJob(submission),
  getJobStatus: (jobId) => getJobStatus(jobId),
  artifactDownloadUrl: (jobId, artifactKey) =>
    artifactDownloadUrl(jobId, artifactKey),
};

type ConnectionState = "checking" | "connected" | "offline";
type WorkflowPhase =
  "editing" | "submitting" | "processing" | "failed" | "completed";

const SOURCE_OPTIONS: Array<{
  value: SourceType;
  label: string;
  aria: string;
}> = [
  { value: "youtube", label: "YouTube", aria: "YouTube 網址來源" },
  { value: "mp3", label: "MP3", aria: "MP3 檔案" },
  { value: "mp4", label: "MP4", aria: "MP4 檔案" },
];

const PROFILES: Array<{
  value: WhisperProfile;
  title: string;
  model: string;
  detail: string;
}> = [
  { value: "fast", title: "快速", model: "base.en", detail: "速度優先" },
  { value: "balanced", title: "平衡", model: "small.en", detail: "建議預設" },
  { value: "accurate", title: "精準", model: "medium.en", detail: "品質優先" },
];

const STAGE_LABELS: Record<JobStage, string> = {
  PENDING: "等待開始",
  DOWNLOADING: "下載 YouTube 媒體",
  EXTRACTING_AUDIO: "準備音訊",
  TRANSCRIBING: "Local Whisper 轉錄",
  TRANSLATING: "翻譯為繁體中文",
  GENERATING_SUBTITLES: "產生字幕",
  GENERATING_SUMMARY: "產生摘要",
  COMPLETED: "完成",
  FAILED: "失敗",
};

const ARTIFACT_LABELS: Record<string, string> = {
  english_transcript: "英文逐字稿",
  traditional_chinese_transcript: "繁體中文逐字稿",
  english_srt: "英文 SRT",
  traditional_chinese_srt: "繁體中文 SRT",
  bilingual_srt: "雙語 SRT",
  english_summary: "英文摘要",
  traditional_chinese_summary: "繁體中文摘要",
};

const MAX_UPLOAD_BYTES = 1_073_741_824;

export function Phase1Workflow({
  api = defaultApi,
  pollSchedule = [750, 1_500, 3_000, 5_000],
}: {
  api?: WorkflowApi;
  pollSchedule?: readonly number[];
}) {
  const [connection, setConnection] = useState<ConnectionState>("checking");
  const [providerConfig, setProviderConfig] =
    useState<LocalProviderConfig | null>(null);
  const [phase, setPhase] = useState<WorkflowPhase>("editing");
  const [sourceType, setSourceType] = useState<SourceType>("youtube");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<WhisperProfile>("balanced");
  const [formError, setFormError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [progress, setProgress] = useState(0);
  const [reconnecting, setReconnecting] = useState(false);
  const [failureGuidance, setFailureGuidance] = useState<string | null>(null);
  const [result, setResult] = useState<Phase1Result | null>(null);
  const stateHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      const healthy = await api.checkHealth();
      if (!active) return;
      setConnection(healthy ? "connected" : "offline");
      if (!healthy) return;
      try {
        const config = await api.getLocalConfig();
        if (active) setProviderConfig(config);
      } catch {
        if (active) setProviderConfig(null);
      }
    })();
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    if (phase !== "editing") stateHeading.current?.focus();
  }, [phase]);

  useEffect(() => {
    if (phase !== "processing" || jobId === null) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    const schedule = pollSchedule.length > 0 ? pollSchedule : [1_000];

    const poll = async () => {
      try {
        const next = await api.getJobStatus(jobId);
        if (!active) return;
        failures = 0;
        setReconnecting(false);
        setStatus(next);
        setProgress((current) => Math.max(current, next.progress));
        if (next.stage === "COMPLETED") {
          if (next.result === null || next.result.artifacts.length !== 7) {
            setFailureGuidance(
              "工作已結束，但完整結果尚未就緒。請建立新工作再試一次。",
            );
            setPhase("failed");
          } else {
            setResult(next.result);
            setPhase("completed");
          }
          return;
        }
        if (next.stage === "FAILED") {
          setFailureGuidance(failureMessage(next.error?.category));
          setPhase("failed");
          return;
        }
        timer = setTimeout(poll, schedule[0]);
      } catch (error) {
        if (!active) return;
        const retryable = !(error instanceof ApiError) || error.retryable;
        if (!retryable) {
          setFailureGuidance("無法讀取工作狀態。請建立新工作再試一次。");
          setPhase("failed");
          return;
        }
        setReconnecting(true);
        failures += 1;
        const delay = schedule[Math.min(failures, schedule.length - 1)];
        timer = setTimeout(poll, delay);
      }
    };

    timer = setTimeout(poll, schedule[0]);
    return () => {
      active = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [api, jobId, phase, pollSchedule]);

  const changeSource = (next: SourceType) => {
    setSourceType(next);
    setYoutubeUrl("");
    setFile(null);
    setFormError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (phase !== "editing" || connection !== "connected") return;
    const error = validateSource(sourceType, youtubeUrl, file);
    if (error !== null) {
      setFormError(error);
      return;
    }
    setFormError(null);
    setPhase("submitting");
    try {
      const submission: JobSubmission =
        sourceType === "youtube"
          ? {
              sourceType,
              youtubeUrl: youtubeUrl.trim(),
              whisperProfile: profile,
            }
          : { sourceType, file: file!, whisperProfile: profile };
      const createdJob = await api.submitJob(submission);
      setJobId(createdJob.job_id);
      setStatus(null);
      setProgress(0);
      setPhase("processing");
    } catch (error) {
      setFormError(
        error instanceof ApiError
          ? error.safeMessage
          : "無法建立處理工作，請檢查本機後端。",
      );
      setPhase("editing");
    }
  };

  const resetForNewJob = () => {
    setPhase("editing");
    setJobId(null);
    setStatus(null);
    setProgress(0);
    setReconnecting(false);
    setFailureGuidance(null);
    setResult(null);
    setFormError(null);
  };

  return (
    <section className="workspace" aria-labelledby="workflow-heading">
      {phase === "editing" || phase === "submitting" ? (
        <JobForm
          connection={connection}
          file={file}
          formError={formError}
          onFile={setFile}
          onProfile={setProfile}
          onSource={changeSource}
          onSubmit={handleSubmit}
          onYoutubeUrl={setYoutubeUrl}
          phase={phase}
          profile={profile}
          providerConfig={providerConfig}
          sourceType={sourceType}
          youtubeUrl={youtubeUrl}
        />
      ) : null}
      {phase === "processing" ? (
        <ProcessingView
          headingRef={stateHeading}
          progress={progress}
          reconnecting={reconnecting}
          sourceType={sourceType}
          status={status}
        />
      ) : null}
      {phase === "failed" ? (
        <FailedView
          guidance={failureGuidance ?? "處理未完成。請建立新工作再試一次。"}
          headingRef={stateHeading}
          onReset={resetForNewJob}
        />
      ) : null}
      {phase === "completed" && result !== null ? (
        <CompletedView api={api} headingRef={stateHeading} result={result} />
      ) : null}
    </section>
  );
}

function JobForm({
  connection,
  file,
  formError,
  onFile,
  onProfile,
  onSource,
  onSubmit,
  onYoutubeUrl,
  phase,
  profile,
  providerConfig,
  sourceType,
  youtubeUrl,
}: {
  connection: ConnectionState;
  file: File | null;
  formError: string | null;
  onFile(value: File | null): void;
  onProfile(value: WhisperProfile): void;
  onSource(value: SourceType): void;
  onSubmit(event: FormEvent<HTMLFormElement>): void;
  onYoutubeUrl(value: string): void;
  phase: WorkflowPhase;
  profile: WhisperProfile;
  providerConfig: LocalProviderConfig | null;
  sourceType: SourceType;
  youtubeUrl: string;
}) {
  return (
    <div className="workflow-panel">
      <div className="workflow-panel__heading">
        <p className="eyebrow">Phase 1 · Local Web UI</p>
        <h2 id="workflow-heading">建立字幕工作</h2>
        <p>媒體只在本機後端處理；語音辨識使用 Local Whisper。</p>
      </div>
      <ConnectionNotice state={connection} />
      <form onSubmit={onSubmit} noValidate>
        <fieldset className="choice-group">
          <legend>1. 選擇來源</legend>
          <div className="segmented-control">
            {SOURCE_OPTIONS.map((option) => (
              <label key={option.value}>
                <input
                  aria-label={option.aria}
                  checked={sourceType === option.value}
                  disabled={phase === "submitting"}
                  name="source-type"
                  onChange={() => onSource(option.value)}
                  type="radio"
                  value={option.value}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="field-block">
          {sourceType === "youtube" ? (
            <label>
              <span>YouTube 網址</span>
              <input
                autoComplete="url"
                disabled={phase === "submitting"}
                onChange={(event) => onYoutubeUrl(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=…"
                type="url"
                value={youtubeUrl}
              />
            </label>
          ) : (
            <label>
              <span>選擇 {sourceType.toUpperCase()} 檔案</span>
              <input
                aria-label={`選擇 ${sourceType.toUpperCase()} 檔案`}
                accept={
                  sourceType === "mp3" ? ".mp3,audio/mpeg" : ".mp4,video/mp4"
                }
                disabled={phase === "submitting"}
                key={sourceType}
                onChange={(event) => onFile(event.target.files?.[0] ?? null)}
                type="file"
              />
              <small>
                {file?.name ?? `單一 ${sourceType.toUpperCase()}，最大 1 GB`}
              </small>
            </label>
          )}
        </div>

        <fieldset className="choice-group profile-group">
          <legend>2. Local Whisper 模式</legend>
          <div className="profile-grid">
            {PROFILES.map((option) => (
              <label key={option.value}>
                <input
                  checked={profile === option.value}
                  disabled={phase === "submitting"}
                  name="profile"
                  onChange={() => onProfile(option.value)}
                  type="radio"
                  value={option.value}
                />
                <span>
                  <strong>{option.title}</strong>
                  <small>
                    {option.model} · {option.detail}
                  </small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="provider-note">
          <strong>翻譯與摘要</strong>
          <span>
            Ollama 相容本機模型：
            {providerConfig?.ollama_model ?? "讀取後端設定中"}
          </span>
        </div>
        {formError !== null ? (
          <p className="form-error" role="alert">
            {formError}
          </p>
        ) : null}
        <button
          className="primary-action"
          disabled={connection !== "connected" || phase === "submitting"}
          type="submit"
        >
          {phase === "submitting" ? "正在建立工作…" : "開始處理"}
        </button>
      </form>
    </div>
  );
}

function ConnectionNotice({ state }: { state: ConnectionState }) {
  if (state === "checking")
    return (
      <p className="connection connection--checking" role="status">
        正在檢查本機後端…
      </p>
    );
  if (state === "connected")
    return (
      <p className="connection connection--ok" role="status">
        本機後端已連線
      </p>
    );
  return (
    <div className="connection connection--offline" role="alert">
      <strong>本機後端未連線</strong>
      <span>請先啟動 FastAPI 後端，再重新整理此頁。</span>
    </div>
  );
}

function ProcessingView({
  headingRef,
  progress,
  reconnecting,
  sourceType,
  status,
}: {
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  progress: number;
  reconnecting: boolean;
  sourceType: SourceType;
  status: JobStatus | null;
}) {
  const stages = Object.keys(STAGE_LABELS).filter(
    (stage): stage is JobStage =>
      !["PENDING", "COMPLETED", "FAILED"].includes(stage) &&
      !(sourceType !== "youtube" && stage === "DOWNLOADING"),
  );
  return (
    <div className="workflow-panel state-panel" aria-live="polite">
      <p className="eyebrow">Local pipeline</p>
      <h2 id="workflow-heading" ref={headingRef} tabIndex={-1}>
        處理進度
      </h2>
      <p className="current-stage">
        {status ? STAGE_LABELS[status.stage] : "等待本機工作器"}
      </p>
      <div
        aria-label="整體處理進度"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={progress}
        className="progress-track"
        role="progressbar"
      >
        <span style={{ width: `${progress}%` }} />
      </div>
      <strong className="progress-value">{progress}%</strong>
      {reconnecting ? (
        <p className="reconnect-notice" role="status">
          連線中斷，正在以退避間隔重新連線…
        </p>
      ) : null}
      <ol className="stage-list">
        {stages.map((stage) => {
          const complete = status?.completed_stages.includes(stage) ?? false;
          const current = status?.stage === stage;
          return (
            <li
              className={complete ? "is-complete" : current ? "is-current" : ""}
              key={stage}
            >
              <span aria-hidden="true">
                {complete ? "✓" : current ? "●" : "○"}
              </span>
              {STAGE_LABELS[stage]}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function FailedView({
  guidance,
  headingRef,
  onReset,
}: {
  guidance: string;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  onReset(): void;
}) {
  return (
    <div className="workflow-panel state-panel failure-panel" role="alert">
      <p className="eyebrow">需要處理</p>
      <h2 id="workflow-heading" ref={headingRef} tabIndex={-1}>
        處理失敗
      </h2>
      <p>{guidance}</p>
      <button className="primary-action" onClick={onReset} type="button">
        修改設定並建立新工作
      </button>
    </div>
  );
}

function CompletedView({
  api,
  headingRef,
  result,
}: {
  api: WorkflowApi;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  result: Phase1Result;
}) {
  const englishSummary = result.summaries.find(
    (summary) => summary.language === "en",
  );
  const chineseSummary = result.summaries.find(
    (summary) => summary.language === "zh-TW",
  );
  return (
    <div className="results" aria-live="polite">
      <div className="workflow-panel result-heading">
        <p className="eyebrow">All local · 7 artifacts</p>
        <h2 id="workflow-heading" ref={headingRef} tabIndex={-1}>
          處理完成
        </h2>
        <p>逐字稿、字幕與摘要已完成，可分別下載。</p>
      </div>
      <div className="result-grid">
        <ResultText title="英文逐字稿">
          {result.transcript.segments.map((segment) => (
            <p key={segment.segment_id}>
              <time>{formatTime(segment.start_ms)}</time>
              {segment.source_text}
            </p>
          ))}
        </ResultText>
        <ResultText title="繁體中文逐字稿">
          {result.translated.segments.map((segment) => (
            <p key={segment.segment_id}>
              <time>{formatTime(segment.start_ms)}</time>
              {segment.translated_text}
            </p>
          ))}
        </ResultText>
        <ResultText title="英文摘要">
          <p>{englishSummary?.text ?? "摘要不可用"}</p>
        </ResultText>
        <ResultText title="繁體中文摘要">
          <p>{chineseSummary?.text ?? "摘要不可用"}</p>
        </ResultText>
      </div>
      <section className="artifact-panel" aria-labelledby="downloads-heading">
        <div>
          <p className="eyebrow">Downloads</p>
          <h3 id="downloads-heading">七項輸出檔案</h3>
        </div>
        <ul className="artifact-list">
          {result.artifacts.map((artifact) => (
            <li key={artifact.artifact_key}>
              <div>
                <strong>{ARTIFACT_LABELS[artifact.kind]}</strong>
                <small>
                  {artifact.filename} · {formatBytes(artifact.size_bytes)}
                </small>
              </div>
              <a
                download={artifact.filename}
                href={api.artifactDownloadUrl(
                  result.job_id,
                  artifact.artifact_key,
                )}
              >
                下載 {ARTIFACT_LABELS[artifact.kind]}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ResultText({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <section className="result-card">
      <h3>{title}</h3>
      <div className="result-card__body">{children}</div>
    </section>
  );
}

function validateSource(
  sourceType: SourceType,
  youtubeUrl: string,
  file: File | null,
): string | null {
  if (sourceType === "youtube") {
    try {
      const url = new URL(youtubeUrl.trim());
      if (
        !["http:", "https:"].includes(url.protocol) ||
        !["youtube.com", "www.youtube.com", "youtu.be"].includes(
          url.hostname.toLowerCase(),
        )
      )
        throw new Error();
      return null;
    } catch {
      return "請輸入有效的 YouTube 網址。";
    }
  }
  if (file === null) return `請選擇一個 ${sourceType.toUpperCase()} 檔案。`;
  if (file.size === 0) return "檔案不可為空。";
  if (file.size > MAX_UPLOAD_BYTES) return "檔案超過 1 GB 上限。";
  if (!file.name.toLowerCase().endsWith(`.${sourceType}`))
    return `檔案副檔名必須是 .${sourceType}。`;
  return null;
}

function failureMessage(category?: string): string {
  if (category === "ollama_unavailable")
    return "Ollama 本機服務或模型目前不可用；請確認後端 readiness 後建立新工作。";
  if (category === "whisper_unavailable")
    return "Local Whisper 模型目前不可用；請確認模型檔案後建立新工作。";
  if (category === "source_unavailable")
    return "來源目前無法取得；請確認 YouTube 公開狀態或改用本機檔案。";
  if (category === "media_invalid")
    return "媒體無法解析；請確認檔案可播放且含有音訊。";
  return "本機處理未完成；請檢查後端 readiness 後建立新工作。";
}

function formatTime(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1_000);
  const hours = Math.floor(totalSeconds / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;
  return `[${[hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":")}]`;
}

function formatBytes(bytes: number): string {
  return bytes < 1_024 ? `${bytes} B` : `${(bytes / 1_024).toFixed(1)} KB`;
}
