// Helpers for calling the backend. Every request goes to /api/...,
// which the Vite dev server forwards to FastAPI (see vite.config.ts).
//
// Access tokens expire after 15 minutes. When a request gets "401 Not authenticated", the
// matching refresh token is swapped for new tokens once (POST /auth/refresh) and the request is
// repeated. If that fails too, the session is removed and the app shows the login form again.

import { getSession, kindOfToken, setSession } from "./session";
import type { SessionKind } from "./session";
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

function send(method: string, path: string, token?: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`/api${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

// One renewal at a time per session, even if several requests fail together.
const renewals: Partial<Record<SessionKind, Promise<string | null>>> = {};

async function renewAccessToken(oldToken: string): Promise<string | null> {
  const kind = kindOfToken(oldToken);
  const session = kind ? getSession(kind) : null;
  if (!kind || !session) return null;
  renewals[kind] ??= (async () => {
    try {
      const response = await send("POST", "/auth/refresh", undefined, {
        refresh_token: session.refreshToken,
      });
      if (!response.ok) {
        setSession(kind, null); // refresh token expired too: log out
        return null;
      }
      const tokens = (await response.json()) as Tokens;
      setSession(kind, { ...session, token: tokens.access_token, refreshToken: tokens.refresh_token });
      return tokens.access_token;
    } catch {
      return null; // network error: keep the session, the caller shows the error
    } finally {
      delete renewals[kind];
    }
  })();
  return renewals[kind]!;
}

export async function apiRequest<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  let response = await send(method, path, options.token, options.body);
  if (response.status === 401 && options.token) {
    const renewed = await renewAccessToken(options.token);
    if (renewed) response = await send(method, path, renewed, options.body);
  }

  if (!response.ok) {
    let message = `${method} ${path} failed with status ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail; // FastAPI error text
    } catch {
      // the error body was not JSON; keep the generic message
    }
    if (response.status === 401 && options.token) {
      message = "Your session has ended. Please log in again.";
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
  return { token: tokens.access_token, refreshToken: tokens.refresh_token, user };
}
