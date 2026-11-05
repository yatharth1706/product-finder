/**
 * Thin HTTP client for the Product Finder backend.
 * All backend calls go through `request` so error handling stays in one place.
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Backend is unavailable. Please try again shortly.", 0, "backend_unavailable");
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message = body?.error?.message ?? `Request failed (${response.status}).`;
    throw new ApiError(message, response.status, body?.error?.code);
  }
  return body as T;
}

export function getHealth(): Promise<{ status: string }> {
  return request("/health");
}
