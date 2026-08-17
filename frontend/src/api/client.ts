/**
 * HTTP client.
 *
 * Security decisions worth knowing about:
 *
 *  - The access token lives in memory only (see `stores/auth.ts`). It is never
 *    written to localStorage or sessionStorage, so an XSS payload cannot read a
 *    long-lived credential out of storage.
 *  - The refresh token is an HttpOnly cookie the browser attaches on its own;
 *    JavaScript never sees it. `credentials: 'include'` is what lets the cookie
 *    travel to the API origin.
 *  - Cookie-authenticated calls (refresh, logout) send the CSRF token from the
 *    readable `lh_csrf` cookie in the `X-CSRF-Token` header.
 *  - A 401 triggers exactly one refresh attempt, shared by every in-flight
 *    request, and the original request is replayed once.
 */

import type { ApiErrorBody, ApiSuccess, FieldError } from './types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '');
const CSRF_COOKIE = 'lh_csrf';
const CSRF_HEADER = 'X-CSRF-Token';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    requestId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** Field-level errors, ready to feed into react-hook-form's `setError`. */
  get fieldErrors(): FieldError[] {
    if (Array.isArray(this.details)) {
      return this.details.filter(
        (item): item is FieldError =>
          typeof item === 'object' && item !== null && 'field' in item && 'message' in item,
      );
    }
    if (this.details && typeof this.details === 'object' && 'field' in this.details) {
      const detail = this.details as { field: string };
      return [{ field: detail.field, message: this.message }];
    }
    return [];
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }

  get retryAfterSeconds(): number | null {
    if (this.details && typeof this.details === 'object' && 'retry_after_seconds' in this.details) {
      return Number((this.details as { retry_after_seconds: number }).retry_after_seconds);
    }
    return null;
  }
}

export function readCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/([.*+?^${}()|[\]\\])/g, '\\$1')}=([^;]*)`),
  );
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

/* -------------------------------------------------------------------------- */
/* Token plumbing                                                             */
/*                                                                            */
/* The auth store registers callbacks here rather than the client importing    */
/* the store, which would create a cycle.                                      */
/* -------------------------------------------------------------------------- */

let getAccessToken: () => string | null = () => null;
let onSessionRefreshed: (session: unknown) => void = () => {};
let onSessionLost: () => void = () => {};

export function configureAuthBridge(options: {
  getAccessToken: () => string | null;
  onSessionRefreshed: (session: unknown) => void;
  onSessionLost: () => void;
}): void {
  getAccessToken = options.getAccessToken;
  onSessionRefreshed = options.onSessionRefreshed;
  onSessionLost = options.onSessionLost;
}

let refreshPromise: Promise<boolean> | null = null;

/** Single-flight refresh: concurrent 401s wait on one network call. */
async function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const csrf = readCookie(CSRF_COOKIE);
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: csrf ? { [CSRF_HEADER]: csrf } : {},
      });
      if (!response.ok) return false;
      const body = (await response.json()) as ApiSuccess<unknown>;
      onSessionRefreshed(body.data);
      return true;
    } catch {
      return false;
    } finally {
      // Cleared on the next tick so callers that already awaited get the result.
      setTimeout(() => {
        refreshPromise = null;
      }, 0);
    }
  })();

  return refreshPromise;
}

/* -------------------------------------------------------------------------- */
/* Request                                                                    */
/* -------------------------------------------------------------------------- */

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  /** Skip the automatic refresh-and-retry (used by auth calls themselves). */
  skipAuthRetry?: boolean;
  query?: Record<string, string | number | boolean | null | undefined>;
  raw?: boolean;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(
    `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`,
    window.location.origin,
  );
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    /* non-JSON error (proxy timeout, gateway page) */
  }

  if (body && 'error' in body && body.error) {
    return new ApiError(
      response.status,
      body.error.code,
      body.error.message,
      body.error.details,
      body.error.request_id,
    );
  }

  const fallback: Record<number, string> = {
    0: 'Cannot reach the server. Check your connection.',
    401: 'Please sign in to continue.',
    403: 'You do not have permission to do that.',
    404: 'We could not find what you were looking for.',
    413: 'That file is too large.',
    429: 'Too many requests. Please wait a moment.',
    500: 'Something went wrong on our side.',
    502: 'The server is unavailable. Try again shortly.',
    503: 'The service is temporarily unavailable.',
  };
  return new ApiError(
    response.status,
    'HTTP_ERROR',
    fallback[response.status] ?? `Request failed (${response.status})`,
  );
}

async function performRequest(path: string, options: RequestOptions): Promise<Response> {
  const { body, query, skipAuthRetry: _skip, raw: _raw, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  finalHeaders.set('Accept', 'application/json');

  const token = getAccessToken();
  if (token) finalHeaders.set('Authorization', `Bearer ${token}`);

  const csrf = readCookie(CSRF_COOKIE);
  if (csrf) finalHeaders.set(CSRF_HEADER, csrf);

  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    // Let the browser set the multipart boundary.
    payload = body;
  } else if (body !== undefined) {
    finalHeaders.set('Content-Type', 'application/json');
    payload = JSON.stringify(body);
  }

  return fetch(buildUrl(path, query), {
    ...rest,
    headers: finalHeaders,
    body: payload,
    credentials: 'include',
  });
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await performRequest(path, options);
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection.');
  }

  if (response.status === 401 && !options.skipAuthRetry) {
    const refreshed = await refreshSession();
    if (refreshed) {
      try {
        response = await performRequest(path, options);
      } catch {
        throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server.');
      }
    } else {
      onSessionLost();
      throw await toApiError(response);
    }
  }

  if (!response.ok) throw await toApiError(response);

  if (response.status === 204) return undefined as T;
  if (options.raw) return response as unknown as T;

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    return (await response.blob()) as unknown as T;
  }
  return (await response.json()) as T;
}

/** Unwraps `{success, data}` so callers work with the payload directly. */
export async function apiGet<T>(path: string, query?: RequestOptions['query']): Promise<T> {
  const body = await request<ApiSuccess<T>>(path, { method: 'GET', query });
  return body.data;
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  const response = await request<ApiSuccess<T>>(path, { ...options, method: 'POST', body });
  return response.data;
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const response = await request<ApiSuccess<T>>(path, { method: 'PATCH', body });
  return response.data;
}

export async function apiDelete<T = { message: string }>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' });
}

export async function apiMessage(
  path: string,
  method: 'POST' | 'DELETE' = 'POST',
  body?: unknown,
): Promise<string> {
  const response = await request<{ message: string }>(path, { method, body });
  return response.message;
}

/** Fetch a binary asset (QR download) with authentication applied. */
export async function apiBlob(
  path: string,
  query?: RequestOptions['query'],
): Promise<Blob> {
  const response = await performRequest(path, { method: 'GET', query });
  if (response.status === 401) {
    if (await refreshSession()) {
      const retry = await performRequest(path, { method: 'GET', query });
      if (!retry.ok) throw await toApiError(retry);
      return retry.blob();
    }
    onSessionLost();
  }
  if (!response.ok) throw await toApiError(response);
  return response.blob();
}

export { API_BASE_URL };
