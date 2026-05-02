/**
 * Prefer IPv4 for hostname "localhost" so browser HTTP/WS targets match a typical
 * Uvicorn bind (127.0.0.1), avoiding ws://localhost → ::1 connection refused on Windows.
 */
function normalizeApiOrigin(url: string): string {
  try {
    const u = new URL(url);
    if (u.hostname === "localhost") {
      u.hostname = "127.0.0.1";
      return u.toString().replace(/\/$/, "");
    }
  } catch {
    /* keep as-is */
  }
  return url.replace(/\/$/, "");
}

/**
 * API base URL for the recruiter backend.
 * Prefer `NEXT_PUBLIC_API_URL` (full URL). Otherwise build from host/port/protocol (see `.env.example`).
 */
function resolveApiBase(): string {
  const explicit = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (explicit) {
    return normalizeApiOrigin(explicit);
  }

  const protocol = (process.env.NEXT_PUBLIC_API_PROTOCOL ?? "http").replace(/:$/, "");
  const host = process.env.NEXT_PUBLIC_API_HOST ?? "127.0.0.1";
  const port = process.env.NEXT_PUBLIC_API_PORT ?? "8000";
  return normalizeApiOrigin(`${protocol}://${host}:${port}`);
}

export const API_BASE = resolveApiBase();

/** WebSocket base derived from API_BASE (e.g. ws://host:port). */
export function apiWsBase(): string {
  const override = process.env.NEXT_PUBLIC_WS_URL?.trim();
  if (override) {
    return override.replace(/\/$/, "");
  }
  if (API_BASE.startsWith("https://")) {
    return `wss://${API_BASE.slice("https://".length)}`;
  }
  if (API_BASE.startsWith("http://")) {
    return `ws://${API_BASE.slice("http://".length)}`;
  }
  return API_BASE;
}
