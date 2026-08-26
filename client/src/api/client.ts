const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8081";

const TOKEN_KEY = "gearledger_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

interface RequestOptions {
  method?: string;
  body?: BodyInit;
  isJson?: boolean;
}

export async function apiFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const { method = "GET", body, isJson = true } = options;
  const token = getToken();
  const headers: Record<string, string> = {};
  if (isJson && body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body });

  if (response.status === 401) {
    clearToken();
    onUnauthorized?.();
  }

  return response;
}

export async function apiJson<T>(path: string, options?: RequestOptions): Promise<T> {
  const response = await apiFetch(path, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      (data && typeof data === "object" && "error" in data && String(data.error)) ||
      `Request failed (${response.status})`;
    throw new ApiError(response.status, message);
  }
  return data as T;
}
