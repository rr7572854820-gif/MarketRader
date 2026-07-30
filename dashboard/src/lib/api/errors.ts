/**
 * A single error type for every failure mode the API client can hit,
 * so every page can handle "the request failed" one way instead of
 * juggling fetch's TypeError-on-network-failure vs. a parsed HTTP
 * error body vs. a JSON-parse failure.
 */
export class ApiError extends Error {
  /** null for a network-level failure (couldn't reach the server at all) - never null for an HTTP response. */
  readonly status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  get isNetworkError(): boolean {
    return this.status === null;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isValidationError(): boolean {
    return this.status === 422;
  }
}

/** FastAPI's own error body shape: either {"detail": "message"} (most
 * handlers) or {"detail": [{"loc": [...], "msg": "...", ...}, ...]}
 * (Pydantic validation errors, e.g. an out-of-range `limit`). Normalized
 * into one readable string so callers never need to know which shape
 * they got.
 */
export function formatErrorDetail(body: unknown): string | null {
  if (body === null || typeof body !== "object" || !("detail" in body)) {
    return null;
  }
  const detail = (body as { detail: unknown }).detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = "loc" in item && Array.isArray(item.loc) ? item.loc.join(".") : null;
          const msg = String((item as { msg: unknown }).msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return null;
      })
      .filter((m): m is string => m !== null);
    return messages.length > 0 ? messages.join("; ") : null;
  }

  return null;
}
