const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ADMIN_TOKEN_KEY = "echolearn_admin_token";

let adminToken: string | null = null;

export function setAdminToken(token: string | null) {
  adminToken = token;
  try {
    if (token) sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    else sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function getAdminToken(): string | null {
  if (adminToken) return adminToken;
  try {
    adminToken = sessionStorage.getItem(ADMIN_TOKEN_KEY);
  } catch {
    adminToken = null;
  }
  return adminToken;
}

export class AdminApiError extends Error {
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

interface RequestOptions extends RequestInit {}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { headers, ...rest } = options;
  const token = getAdminToken();

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string>),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_URL}${path}`, { ...rest, headers: finalHeaders });

  if (!res.ok) {
    throw new AdminApiError(res.status, await parseError(res));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const adminApi = {
  get: <T,>(path: string) => request<T>(path, { method: "GET" }),
  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "DELETE", body: body ? JSON.stringify(body) : undefined }),
};
