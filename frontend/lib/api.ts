const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let accessToken: string | null = null;
// When the current access token was issued (ms). Access tokens live 15 minutes on the
// server, so the app renews them in the background before they expire.
let tokenIssuedAt = 0;

export function setAccessToken(token: string | null) {
  accessToken = token;
  tokenIssuedAt = token ? Date.now() : 0;
}

export function getAccessToken() {
  return accessToken;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return data.detail || data.error || res.statusText;
  } catch {
    return res.statusText;
  }
}

interface RequestOptions extends RequestInit {
  auth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}, retry = true): Promise<T> {
  const { auth = false, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string>),
  };

  if (auth && accessToken) {
    finalHeaders["Authorization"] = `Bearer ${accessToken}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    credentials: "include",
  });

  if (res.status === 401 && auth && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return request<T>(path, options, false);
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

// Concurrent callers share one in-flight refresh instead of each sending their own.
let refreshing: Promise<boolean> | null = null;

function tryRefresh(): Promise<boolean> {
  if (!refreshing) refreshing = doRefresh().finally(() => (refreshing = null));
  return refreshing;
}

/** Renew the access token if it's older than `maxAgeMs` (e.g. after the laptop slept). */
export async function refreshIfStale(maxAgeMs: number): Promise<void> {
  if (accessToken && Date.now() - tokenIssuedAt > maxAgeMs) await tryRefresh();
}

/**
 * fetch() for authenticated calls that need the raw Response (streaming, file uploads,
 * downloads). Adds the access token, and if the server says it expired (401), renews it
 * once and retries. Use this instead of calling fetch() with a hand-built Authorization
 * header, which fails as soon as the 15-minute token runs out.
 */
export async function authFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const url = /^https?:\/\//.test(path) ? path : `${API_URL}${path}`;
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  const res = await fetch(url, { ...init, headers, credentials: "include" });
  if (res.status === 401 && retry && (await tryRefresh())) return authFetch(path, init, false);
  return res;
}

async function doRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/auth/refresh-token`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return false;
    const data = await res.json();
    setAccessToken(data.access_token);
    return true;
  } catch {
    return false;
  }
}

export function getMediaUrl(documentId: string): string {
  const token = accessToken ? `?token=${encodeURIComponent(accessToken)}` : "";
  return `${API_URL}/documents/${documentId}/media${token}`;
}

export const api = {
  get: <T,>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "GET" }),
  post: <T,>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T,>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T,>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "DELETE" }),
};

export { tryRefresh };
