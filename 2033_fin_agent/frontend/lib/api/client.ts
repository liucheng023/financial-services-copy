const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

type Json = Record<string, unknown>;

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const url = `${backendUrl}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    let detail: string = body;
    try {
      const parsed = JSON.parse(body);
      detail = parsed.detail?.detail ?? parsed.detail ?? body;
    } catch {
      // not JSON, use raw text
    }
    throw new Error(`API ${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const apiClient = {
  GET: <T>(path: string) => request<T>(path),

  POST: <T>(path: string, body?: Json) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),

  POST_SSE: (path: string, body: Json) =>
    fetch(`${backendUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};
