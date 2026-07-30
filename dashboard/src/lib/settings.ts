/**
 * Small localStorage-backed settings, read by both the Settings page
 * and the API client. Deliberately not a React context - the only
 * consumer that needs live reactivity is the Settings page itself
 * (which owns its own React state and writes through these functions);
 * the API client just needs the current value at call time, which a
 * plain function read gives it without provider wiring.
 */

const API_BASE_URL_KEY = "marketradar:api-base-url";
const DEFAULT_MOCK_MODE_KEY = "marketradar:default-mock-mode";

const FALLBACK_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

/** SSR-safe: localStorage does not exist on the server, so server-
 * rendered output always uses the build-time default; client components
 * re-read this after mount (in a useEffect) to pick up any override.
 */
export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return FALLBACK_API_BASE_URL;
  }
  const stored = window.localStorage.getItem(API_BASE_URL_KEY);
  return stored && stored.trim() ? stored.trim().replace(/\/$/, "") : FALLBACK_API_BASE_URL;
}

export function setApiBaseUrl(value: string): void {
  const trimmed = value.trim().replace(/\/$/, "");
  if (!trimmed) {
    window.localStorage.removeItem(API_BASE_URL_KEY);
    return;
  }
  window.localStorage.setItem(API_BASE_URL_KEY, trimmed);
}

export function getDefaultApiBaseUrl(): string {
  return FALLBACK_API_BASE_URL;
}

export function getDefaultMockMode(): boolean {
  if (typeof window === "undefined") {
    return true;
  }
  const stored = window.localStorage.getItem(DEFAULT_MOCK_MODE_KEY);
  return stored === null ? true : stored === "true";
}

export function setDefaultMockMode(value: boolean): void {
  window.localStorage.setItem(DEFAULT_MOCK_MODE_KEY, String(value));
}
