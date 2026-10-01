/** Typed client for the RepoGrill backend API. */

import type {
  AnswerResponse,
  Difficulty,
  DossierResponse,
  IngestResponse,
  InterviewLength,
  SessionResponse,
  SessionState,
  TranscriptionResponse,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }
}

interface ErrorBody {
  error?: string;
  detail?: unknown;
  retry_after?: number;
}

function describeDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Invalid request";
  return fallback;
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {};
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    // Non-JSON error body: fall back to the status text below.
  }
  const header = Number(response.headers.get("retry-after"));
  const retryAfter = body.retry_after ?? (Number.isFinite(header) && header > 0 ? header : null);
  return new ApiError(
    describeDetail(body.detail, response.statusText || "Request failed"),
    response.status,
    body.error ?? "http_error",
    retryAfter,
  );
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError("Cannot reach the RepoGrill server", 0, "network_error");
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export interface Health {
  status: "ok";
}

export function getHealth(signal?: AbortSignal): Promise<Health> {
  return request<Health>("/api/health", { signal });
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function ingestRepo(repoUrl: string): Promise<IngestResponse> {
  return request<IngestResponse>("/api/ingest", json({ repo_url: repoUrl }));
}

export function getDossier(repoId: string): Promise<DossierResponse> {
  return request<DossierResponse>(`/api/dossier/${encodeURIComponent(repoId)}`);
}

export function createSession(
  repoId: string,
  length: InterviewLength,
  difficulty: Difficulty,
): Promise<SessionResponse> {
  return request<SessionResponse>("/api/session", json({ repo_id: repoId, length, difficulty }));
}

export function getSession(sessionId: string): Promise<SessionState> {
  return request<SessionState>(`/api/session/${encodeURIComponent(sessionId)}`);
}

export function submitAnswer(sessionId: string, text: string): Promise<AnswerResponse> {
  return request<AnswerResponse>(
    `/api/session/${encodeURIComponent(sessionId)}/answer`,
    json({ text }),
  );
}

export function endSession(sessionId: string): Promise<AnswerResponse> {
  return request<AnswerResponse>(`/api/session/${encodeURIComponent(sessionId)}/end`, {
    method: "POST",
  });
}

export function transcribe(audio: Blob, durationSeconds: number): Promise<TranscriptionResponse> {
  const form = new FormData();
  const extension = audio.type.includes("ogg")
    ? "ogg"
    : audio.type.includes("mp4")
      ? "m4a"
      : "webm";
  form.append("audio", audio, `answer.${extension}`);
  form.append("duration_seconds", durationSeconds.toFixed(1));
  return request<TranscriptionResponse>("/api/transcribe", { method: "POST", body: form });
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run `call`, and when the server reports a rate limit, wait and retry.
 * `onRateLimited` lets the UI show a "rate limited, retrying…" state.
 */
export async function withRateLimitRetry<T>(
  call: () => Promise<T>,
  onRateLimited: (waitSeconds: number) => void,
  maxRetries = 3,
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await call();
    } catch (error) {
      if (!(error instanceof ApiError) || !error.isRateLimited || attempt >= maxRetries) {
        throw error;
      }
      const wait = Math.min(Math.max(error.retryAfter ?? 10, 2), 60);
      onRateLimited(wait);
      await sleep(wait * 1000);
    }
  }
}
