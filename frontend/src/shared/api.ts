// Helpers for calling the backend. Every request goes to /api/...,
// which the Vite dev server forwards to FastAPI (see vite.config.ts).

import type { Session, Tokens, User } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type RequestOptions = { token?: string; body?: unknown };

export async function apiRequest<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let message = `${method} ${path} failed with status ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail; // FastAPI error text
    } catch {
      // the error body was not JSON; keep the generic message
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function apiGet<T>(path: string, token?: string): Promise<T> {
  return apiRequest<T>("GET", path, { token });
}

// Log in, then ask the backend who we are (to learn our role).
export async function login(email: string, password: string): Promise<Session> {
  const tokens = await apiRequest<Tokens>("POST", "/auth/login", {
    body: { email, password },
  });
  const user = await apiGet<User>("/auth/me", tokens.access_token);
  return { token: tokens.access_token, user };
}
