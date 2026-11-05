import type { JobStatus, SearchJob } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    throw new ApiError("Could not reach the server. Is the backend running?");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new ApiError(detail ?? `Request failed (${response.status})`);
  }
  return body as T;
}

export function createSearch(amazonUrl: string) {
  return request<{ search_id: string; status: JobStatus }>("/api/v1/search", {
    method: "POST",
    body: JSON.stringify({ amazon_url: amazonUrl }),
  });
}

export function getSearch(searchId: string) {
  return request<SearchJob>(`/api/v1/search/${searchId}`);
}
