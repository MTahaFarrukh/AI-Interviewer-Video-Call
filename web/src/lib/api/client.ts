export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    const detail =
      typeof payload === "object" &&
      payload &&
      "detail" in payload &&
      typeof (payload as { detail: unknown }).detail === "string"
        ? (payload as { detail: string }).detail
        : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}

export function getApiBaseUrl() {
  return API_URL;
}
