import type { SearchEvent } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

/**
 * Starts a search and calls `onEvent` for each step as the backend sends it:
 * the Amazon product first, then one result per marketplace as each finishes.
 */
export async function streamSearch(
  amazonUrl: string,
  onEvent: (event: SearchEvent) => void,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/search/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amazon_url: amazonUrl }),
    });
  } catch {
    throw new ApiError("Could not reach the server. Is the backend running?");
  }
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new ApiError(detail ?? `Request failed (${response.status})`);
  }

  // One JSON event per line; a chunk can end in the middle of a line.
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line) as SearchEvent);
    }
  }
}
