import { API_BASE_URL, CACHE_TTL_MS, REQUEST_TIMEOUT_MS } from '@/config';

export type ApiErrorKind = 'offline' | 'timeout' | 'http' | 'parse' | 'aborted';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
  }
}

type QueryValue = string | number | boolean | null | undefined;

export function buildUrl(path: string, params?: Record<string, QueryValue>): string {
  const search = Object.entries(params ?? {})
    .filter(([, value]) => value !== null && value !== undefined && `${value}`.length > 0)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&');
  return `${API_BASE_URL}${path}${search ? `?${search}` : ''}`;
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export interface RequestOptions {
  params?: Record<string, QueryValue>;
  /** Only GET and POST are used; the public API has no other verbs. */
  method?: 'GET' | 'POST';
  signal?: AbortSignal;
  timeoutMs?: number;
  retries?: number;
  /** Treat a 404 as a normal result instead of an error. */
  allowNotFound?: boolean;
}

function describeFetchFailure(error: unknown, timedOut: boolean): ApiError {
  if (timedOut) {
    return new ApiError('timeout', 'The server took too long to respond.');
  }
  const message = error instanceof Error ? error.message : String(error);
  if (/network request failed|failed to fetch|network error|load failed/i.test(message)) {
    return new ApiError('offline', 'No connection to the Bidders Nepal API.');
  }
  return new ApiError('offline', 'Could not reach the Bidders Nepal API.');
}

/**
 * Small fetch wrapper with a hard timeout, retry/backoff for transient
 * failures, and typed errors. No credentials are ever attached.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    params,
    method = 'GET',
    signal,
    timeoutMs = REQUEST_TIMEOUT_MS,
    retries = 1,
    allowNotFound,
  } = options;
  const url = buildUrl(path, params);

  let attempt = 0;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (signal?.aborted) throw new ApiError('aborted', 'Request cancelled.');

    const controller = new AbortController();
    let timedOut = false;
    const abortFromParent = () => controller.abort();
    signal?.addEventListener('abort', abortFromParent);
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    try {
      const response = await fetch(url, {
        method,
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });

      if (response.status === 404 && allowNotFound) {
        throw new ApiError('http', 'Not found', 404);
      }

      if (!response.ok) {
        const retryable = response.status >= 500 || response.status === 429;
        if (retryable && attempt < retries) {
          attempt += 1;
          await wait(700 * attempt);
          continue;
        }
        throw new ApiError(
          'http',
          response.status >= 500
            ? 'The Bidders Nepal API is temporarily unavailable.'
            : `The API responded with status ${response.status}.`,
          response.status,
        );
      }

      const text = await response.text();
      if (!text) return {} as T;
      try {
        return JSON.parse(text) as T;
      } catch {
        throw new ApiError('parse', 'The API returned an unexpected response.');
      }
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.kind === 'http' && error.status && error.status >= 500 && attempt < retries) {
          attempt += 1;
          await wait(700 * attempt);
          continue;
        }
        throw error;
      }
      if (signal?.aborted && !timedOut) throw new ApiError('aborted', 'Request cancelled.');
      const apiError = describeFetchFailure(error, timedOut);
      if (attempt < retries && apiError.kind !== 'aborted') {
        attempt += 1;
        await wait(900 * attempt);
        continue;
      }
      throw apiError;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abortFromParent);
    }
  }
}

interface CacheEntry {
  at: number;
  value: unknown;
}

const cache = new Map<string, CacheEntry>();

export function readCache<T>(key: string, ttl = CACHE_TTL_MS): T | undefined {
  const entry = cache.get(key);
  if (!entry) return undefined;
  if (Date.now() - entry.at > ttl) {
    cache.delete(key);
    return undefined;
  }
  return entry.value as T;
}

export function writeCache(key: string, value: unknown) {
  cache.set(key, { at: Date.now(), value });
}

export function clearApiCache() {
  cache.clear();
}

/** Human-friendly, non-technical error copy for the UI. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.kind) {
      case 'offline':
        return 'You appear to be offline, or the API is waking up. Check your connection and try again.';
      case 'timeout':
        return 'The API is taking longer than usual — free Render hosting can take up to a minute to wake. Please retry.';
      case 'http':
        return error.status && error.status >= 500
          ? 'The Bidders Nepal API is temporarily unavailable. Please try again shortly.'
          : error.message;
      case 'parse':
        return 'The API returned an unexpected response. Please try again.';
      case 'aborted':
        return 'Request cancelled.';
      default:
        return 'Something went wrong while loading tenders.';
    }
  }
  return 'Something went wrong while loading tenders.';
}
