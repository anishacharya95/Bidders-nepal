/**
 * Central runtime configuration.
 *
 * The API base URL is public information (it is the same URL documented in
 * /docs) and contains no credentials. It can be overridden at build time with
 * EXPO_PUBLIC_API_BASE_URL – never put an admin token or password here.
 */
const DEFAULT_API_BASE_URL = 'https://bidders-nepal-api.onrender.com';

function normaliseBaseUrl(value: string | undefined): string {
  const raw = (value ?? '').trim();
  if (!raw) return DEFAULT_API_BASE_URL;
  return raw.replace(/\/+$/, '');
}

export const API_BASE_URL = normaliseBaseUrl(process.env.EXPO_PUBLIC_API_BASE_URL);

/** Public API docs, opened from the Profile screen. */
export const API_DOCS_URL = `${API_BASE_URL}/docs`;

/** The API allows at most 500 records per page on the /all feed. */
export const MAX_PAGE_SIZE = 500;

/** Records rendered per scroll step (client-side paging of the loaded window). */
export const PAGE_STEP = 24;

/** How long a successful read is reused before another network request. */
export const CACHE_TTL_MS = 60_000;

/** Render (cold-start) can take a long time, so be patient with the first call. */
export const REQUEST_TIMEOUT_MS = 45_000;

export const HEALTH_TIMEOUT_MS = 20_000;

export const APP_NAME = 'Bidders Nepal';
export const APP_VERSION = '1.0.0';

/** Days remaining at or below which a tender counts as "closing soon". */
export const CLOSING_SOON_DAYS = 7;
export const CLOSING_SOON_ALERT_DAYS = 3;
