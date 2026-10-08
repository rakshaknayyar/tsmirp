// Small helper for calling the backend. Every request goes to /api/...,
// which the Vite dev server forwards to FastAPI (see vite.config.ts).

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}
