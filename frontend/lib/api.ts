/** Typed client for the RepoGrill backend API. */

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
