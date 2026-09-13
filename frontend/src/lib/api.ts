import { getApiBaseUrl } from "./config";

export const JOB_STAGES = [
  "PENDING",
  "DOWNLOADING",
  "EXTRACTING_AUDIO",
  "TRANSCRIBING",
  "TRANSLATING",
  "GENERATING_SUBTITLES",
  "GENERATING_SUMMARY",
  "COMPLETED",
  "FAILED",
] as const;

export type JobStage = (typeof JOB_STAGES)[number];
export type SourceType = "youtube" | "mp3" | "mp4";
export type WhisperProfile = "fast" | "balanced" | "accurate";

export type JobSubmission =
  | {
      sourceType: "youtube";
      youtubeUrl: string;
      whisperProfile: WhisperProfile;
    }
  | {
      sourceType: "mp3" | "mp4";
      file: File;
      whisperProfile: WhisperProfile;
    };

export interface JobCreated {
  api_version: "1";
  job_id: string;
  status_url: string;
}

export interface TranscriptSegment {
  segment_id: string;
  start_ms: number;
  end_ms: number;
  source_text: string;
}

export interface TranslatedSegment {
  segment_id: string;
  start_ms: number;
  end_ms: number;
  translated_text: string;
}

export type ArtifactKind =
  | "english_transcript"
  | "traditional_chinese_transcript"
  | "english_srt"
  | "traditional_chinese_srt"
  | "bilingual_srt"
  | "english_summary"
  | "traditional_chinese_summary";

export interface ArtifactEntry {
  artifact_key: string;
  kind: ArtifactKind;
  filename: string;
  media_type: string;
  size_bytes: number;
}

export interface Phase1Result {
  schema_version: "1.0";
  job_id: string;
  transcript: { language: "en"; segments: TranscriptSegment[] };
  translated: { language: "zh-TW"; segments: TranslatedSegment[] };
  summaries: Array<{ language: "en" | "zh-TW"; text: string }>;
  artifacts: ArtifactEntry[];
}

export interface JobStatus {
  api_version: "1";
  job_id: string;
  stage: JobStage;
  stage_label: string;
  progress: number;
  completed_stages: JobStage[];
  error: {
    category: string;
    stage: JobStage | null;
    message: string;
  } | null;
  result: Phase1Result | null;
}

export interface LocalProviderConfig {
  api_version: "1";
  speech_provider: "Local Whisper";
  translation_provider: "Ollama-compatible";
  summary_provider: "Ollama-compatible";
  ollama_model: string;
}

export class ApiError extends Error {
  constructor(
    public readonly safeMessage: string,
    public readonly retryable: boolean,
    public readonly status?: number,
  ) {
    super(safeMessage);
    this.name = "ApiError";
  }
}

export async function checkBackendHealth(
  configuredBaseUrl?: string,
): Promise<boolean> {
  try {
    const response = await fetch(`${baseUrl(configuredBaseUrl)}/health`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return false;
    const body: unknown = await response.json();
    return isRecord(body) && body.status === "ok";
  } catch {
    return false;
  }
}

export async function getLocalConfig(
  configuredBaseUrl?: string,
): Promise<LocalProviderConfig> {
  const response = await request(`${baseUrl(configuredBaseUrl)}/api/config`, {
    headers: { Accept: "application/json" },
  });
  const body = await parseJson(response);
  if (!response.ok) {
    throw responseError(response, body, "無法取得本機模型設定。");
  }
  if (
    !isRecord(body) ||
    body.api_version !== "1" ||
    body.speech_provider !== "Local Whisper" ||
    body.translation_provider !== "Ollama-compatible" ||
    body.summary_provider !== "Ollama-compatible" ||
    !isString(body.ollama_model)
  ) {
    throw invalidResponse();
  }
  return body as unknown as LocalProviderConfig;
}

export async function submitJob(
  submission: JobSubmission,
  configuredBaseUrl?: string,
): Promise<JobCreated> {
  const form = new FormData();
  form.set("source_type", submission.sourceType);
  form.set("whisper_profile", submission.whisperProfile);
  if (submission.sourceType === "youtube") {
    form.set("youtube_url", submission.youtubeUrl);
  } else {
    form.set("upload", submission.file);
  }

  const response = await request(`${baseUrl(configuredBaseUrl)}/api/jobs`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: form,
  });
  const body = await parseJson(response);
  if (!response.ok) {
    throw responseError(response, body, "無法建立處理工作。");
  }
  if (
    !isRecord(body) ||
    body.api_version !== "1" ||
    !isString(body.job_id) ||
    !isString(body.status_url)
  ) {
    throw invalidResponse();
  }
  return body as unknown as JobCreated;
}

export async function getJobStatus(
  jobId: string,
  configuredBaseUrl?: string,
): Promise<JobStatus> {
  const response = await request(
    `${baseUrl(configuredBaseUrl)}/api/jobs/${encodeURIComponent(jobId)}`,
    { headers: { Accept: "application/json" } },
  );
  const body = await parseJson(response);
  if (!response.ok) {
    throw responseError(response, body, "無法取得工作狀態。");
  }
  if (!isJobStatus(body)) {
    throw invalidResponse();
  }
  return body;
}

export function artifactDownloadUrl(
  jobId: string,
  artifactKey: string,
  configuredBaseUrl?: string,
): string {
  return `${baseUrl(configuredBaseUrl)}/api/jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(artifactKey)}`;
}

function baseUrl(configuredBaseUrl?: string): string {
  return getApiBaseUrl(configuredBaseUrl).replace(/\/$/, "");
}

async function request(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch {
    throw new ApiError("暫時無法連線到本機後端。", true);
  }
}

async function parseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    if (!response.ok) {
      throw responseError(response, undefined, "後端暫時無法處理要求。");
    }
    throw invalidResponse();
  }
}

function responseError(
  response: Response,
  body: unknown,
  fallback: string,
): ApiError {
  const retryable =
    response.status === 408 ||
    response.status === 429 ||
    response.status >= 500;
  const detail = safeDetail(body);
  return new ApiError(
    retryable ? "暫時無法連線到本機後端。" : (detail ?? fallback),
    retryable,
    response.status,
  );
}

function safeDetail(body: unknown): string | undefined {
  if (!isRecord(body) || !isString(body.detail)) return undefined;
  const detail = body.detail.trim();
  if (
    detail.length === 0 ||
    detail.length > 240 ||
    /(?:api[_-]?key|token|prompt|[a-z]:\\|\/users\/|\/home\/)/i.test(detail)
  ) {
    return undefined;
  }
  return detail;
}

function invalidResponse(): ApiError {
  return new ApiError("後端回應格式無效。", false);
}

function isJobStatus(value: unknown): value is JobStatus {
  if (!isRecord(value)) return false;
  if (
    value.api_version !== "1" ||
    !isString(value.job_id) ||
    !isStage(value.stage) ||
    !isString(value.stage_label) ||
    !Number.isInteger(value.progress) ||
    Number(value.progress) < 0 ||
    Number(value.progress) > 100 ||
    !Array.isArray(value.completed_stages) ||
    !value.completed_stages.every(isStage)
  ) {
    return false;
  }
  const errorValid = value.error === null || isJobError(value.error);
  const resultValid = value.result === null || isPhase1Result(value.result);
  if (!errorValid || !resultValid) return false;
  if (value.stage === "COMPLETED" && value.result === null) return false;
  return true;
}

function isJobError(value: unknown): boolean {
  return (
    isRecord(value) &&
    isString(value.category) &&
    (value.stage === null || isStage(value.stage)) &&
    isString(value.message)
  );
}

function isPhase1Result(value: unknown): value is Phase1Result {
  if (
    !isRecord(value) ||
    value.schema_version !== "1.0" ||
    !isString(value.job_id) ||
    !isRecord(value.transcript) ||
    value.transcript.language !== "en" ||
    !Array.isArray(value.transcript.segments) ||
    !value.transcript.segments.every(isTranscriptSegment) ||
    !isRecord(value.translated) ||
    value.translated.language !== "zh-TW" ||
    !Array.isArray(value.translated.segments) ||
    !value.translated.segments.every(isTranslatedSegment) ||
    !Array.isArray(value.summaries) ||
    value.summaries.length !== 2 ||
    !value.summaries.every(isSummary) ||
    !Array.isArray(value.artifacts) ||
    value.artifacts.length !== 7 ||
    !value.artifacts.every(isArtifact)
  ) {
    return false;
  }
  return new Set(value.artifacts.map((item) => item.kind)).size === 7;
}

function isTranscriptSegment(value: unknown): boolean {
  return (
    isTimedRecord(value) &&
    isString(value.segment_id) &&
    isString(value.source_text)
  );
}

function isTranslatedSegment(value: unknown): boolean {
  return (
    isTimedRecord(value) &&
    isString(value.segment_id) &&
    isString(value.translated_text)
  );
}

function isTimedRecord(value: unknown): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    Number.isInteger(value.start_ms) &&
    Number.isInteger(value.end_ms) &&
    Number(value.start_ms) >= 0 &&
    Number(value.end_ms) > Number(value.start_ms)
  );
}

function isSummary(value: unknown): boolean {
  return (
    isRecord(value) &&
    (value.language === "en" || value.language === "zh-TW") &&
    isString(value.text)
  );
}

const ARTIFACT_KINDS = new Set<unknown>([
  "english_transcript",
  "traditional_chinese_transcript",
  "english_srt",
  "traditional_chinese_srt",
  "bilingual_srt",
  "english_summary",
  "traditional_chinese_summary",
]);

function isArtifact(value: unknown): value is ArtifactEntry {
  return (
    isRecord(value) &&
    isString(value.artifact_key) &&
    ARTIFACT_KINDS.has(value.kind) &&
    isString(value.filename) &&
    isString(value.media_type) &&
    Number.isInteger(value.size_bytes) &&
    Number(value.size_bytes) >= 0
  );
}

function isStage(value: unknown): value is JobStage {
  return JOB_STAGES.includes(value as JobStage);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
