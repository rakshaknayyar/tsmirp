// Who is logged in. Two separate sessions can exist at once - one in the tourist app and one in
// the authority dashboard - so switching between the two pages does not log anyone out.
//
// Sessions are kept in sessionStorage: they survive a page reload but are forgotten when the
// browser tab is closed. (Trade-off for a prototype: a script injected into the page could read
// them; the API uses short-lived access tokens to limit the damage.)
//
// React components read a session with useSession("tourist" | "staff") and re-render whenever
// it changes - for example after api.ts has silently renewed an expired access token.

import { useSyncExternalStore } from "react";

import type { Session } from "./types";

export type SessionKind = "tourist" | "staff";

const STORAGE_KEY = "tsmirp.sessions";
type Store = Partial<Record<SessionKind, Session>>;

function readStorage(): Store {
  try {
    return JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? "{}") as Store;
  } catch {
    return {}; // storage blocked or corrupted: start logged out
  }
}

let store: Store = readStorage();
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSession(kind: SessionKind): Session | null {
  return store[kind] ?? null;
}

export function setSession(kind: SessionKind, session: Session | null): void {
  store = { ...store };
  if (session) store[kind] = session;
  else delete store[kind];
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // storage unavailable (e.g. private mode): the session still works until reload
  }
  listeners.forEach((listener) => listener());
}

// Which session an access token belongs to (used when the token needs renewing).
export function kindOfToken(token: string): SessionKind | null {
  if (store.tourist?.token === token) return "tourist";
  if (store.staff?.token === token) return "staff";
  return null;
}

export function useSession(kind: SessionKind): Session | null {
  return useSyncExternalStore(subscribe, () => store[kind] ?? null);
}
