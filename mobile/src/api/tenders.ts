import { HEALTH_TIMEOUT_MS, MAX_PAGE_SIZE } from '@/config';
import { apiRequest, ApiError, readCache, writeCache } from '@/api/client';
import type { Tender, TenderFilters, TenderPage, VerificationStatus } from '@/types/tender';

interface FeedRequest {
  filters: TenderFilters;
  page: number;
  pageSize?: number;
  force?: boolean;
  includeRejected?: boolean;
}

function filterParams(filters: TenderFilters) {
  return {
    q: filters.q.trim() || undefined,
    category: filters.category || undefined,
    province: filters.province || undefined,
    district: filters.district || undefined,
    municipality: filters.municipality || undefined,
    status: filters.status || undefined,
    verification_status: filters.verificationStatus || undefined,
    has_documents: filters.hasDocuments ? true : undefined,
  };
}

function cacheKeyFor(path: string, params: Record<string, unknown>) {
  return `${path}?${JSON.stringify(params)}`;
}

function normalisePage(raw: any, requestedPage: number): TenderPage {
  const items = Array.isArray(raw?.items) ? raw.items : Array.isArray(raw) ? raw : [];
  return {
    items: items as Tender[],
    total: typeof raw?.total === 'number' ? raw.total : items.length,
    page: typeof raw?.page === 'number' ? raw.page : requestedPage,
    page_size: typeof raw?.page_size === 'number' ? raw.page_size : items.length,
  };
}

/**
 * Public full-record feed: pending + verified notices, newest first as served
 * by the API. This is the primary feed for the app so nothing is hidden.
 */
export async function fetchAllTenders({
  filters,
  page,
  pageSize = MAX_PAGE_SIZE,
  force,
  includeRejected,
  signal,
}: FeedRequest & { signal?: AbortSignal }): Promise<TenderPage> {
  const params = {
    ...filterParams(filters),
    include_rejected: includeRejected ? true : undefined,
    page,
    page_size: Math.min(pageSize, MAX_PAGE_SIZE),
  };
  const key = cacheKeyFor('/api/v1/tenders/all', params);
  if (!force) {
    const cached = readCache<TenderPage>(key);
    if (cached) return cached;
  }
  const raw = await apiRequest<unknown>('/api/v1/tenders/all', { params, signal });
  const pageData = normalisePage(raw, page);
  writeCache(key, pageData);
  return pageData;
}

/** Verified-only public feed (the API's stricter public listing). */
export async function fetchVerifiedTenders({
  filters,
  page,
  pageSize = 100,
  force,
  signal,
}: FeedRequest & { signal?: AbortSignal }): Promise<TenderPage> {
  const params = {
    ...filterParams(filters),
    page,
    page_size: Math.min(pageSize, 100),
  };
  const key = cacheKeyFor('/api/v1/tenders', params);
  if (!force) {
    const cached = readCache<TenderPage>(key);
    if (cached) return cached;
  }
  const raw = await apiRequest<unknown>('/api/v1/tenders', { params, signal });
  const pageData = normalisePage(raw, page);
  writeCache(key, pageData);
  return pageData;
}

/** Verified tender detail. Throws ApiError(404) when the record is not verified. */
export async function fetchTenderDetail(id: number, signal?: AbortSignal): Promise<Tender> {
  const key = `tender:verified:${id}`;
  const cached = readCache<Tender>(key);
  if (cached) return cached;
  const tender = await apiRequest<Tender>(`/api/v1/tenders/${id}`, { signal, allowNotFound: true });
  writeCache(key, tender);
  return tender;
}

/**
 * Resolve any tender (pending or verified) by scanning the public full feed.
 * The detail endpoint only returns verified records, so pending notices are
 * looked up here instead of being treated as missing.
 */
export async function fetchTenderFromFeed(
  id: number,
  signal?: AbortSignal,
  maxPages = 4,
): Promise<Tender> {
  for (let page = 1; page <= maxPages; page += 1) {
    const data = await fetchAllTenders({
      filters: {
        q: '',
        category: null,
        province: null,
        district: null,
        municipality: null,
        organization: null,
        status: null,
        verificationStatus: null,
        hasDocuments: null,
      },
      page,
      pageSize: MAX_PAGE_SIZE,
      signal,
    });
    const match = data.items.find((item) => item.id === id);
    if (match) return match;
    if (data.items.length === 0 || page * data.page_size >= data.total) break;
  }
  throw new ApiError('http', 'This tender is no longer available in the public feed.', 404);
}

/** Fetch a tender with a verified-detail attempt first, then the public feed. */
export async function fetchAnyTender(id: number, signal?: AbortSignal): Promise<Tender> {
  try {
    return await fetchTenderDetail(id, signal);
  } catch (error) {
    if (error instanceof ApiError && error.kind === 'http' && error.status === 404) {
      return fetchTenderFromFeed(id, signal);
    }
    throw error;
  }
}

export async function fetchLatestTenders(
  limit = 10,
  signal?: AbortSignal,
): Promise<Tender[]> {
  const raw = await apiRequest<{ items?: Tender[] }>('/api/v1/tenders/latest', {
    params: { limit },
    signal,
  });
  return Array.isArray(raw?.items) ? raw.items : [];
}

export async function fetchClosingSoonTenders(
  days = 7,
  limit = 50,
  signal?: AbortSignal,
): Promise<Tender[]> {
  const raw = await apiRequest<{ items?: Tender[] }>('/api/v1/tenders/closing-soon', {
    params: { days, limit },
    signal,
  });
  return Array.isArray(raw?.items) ? raw.items : [];
}

export interface HealthResult {
  ok: boolean;
  latencyMs: number;
  checkedAt: string;
  status?: string;
  error?: string;
}

export async function checkApiHealth(): Promise<HealthResult> {
  const started = Date.now();
  try {
    const raw = await apiRequest<{ status?: string }>('/health', {
      timeoutMs: HEALTH_TIMEOUT_MS,
      retries: 0,
    });
    return {
      ok: raw?.status === 'ok',
      latencyMs: Date.now() - started,
      checkedAt: new Date().toISOString(),
      status: raw?.status,
    };
  } catch (error) {
    return {
      ok: false,
      latencyMs: Date.now() - started,
      checkedAt: new Date().toISOString(),
      error: error instanceof Error ? error.message : 'Unreachable',
    };
  }
}

/** Verify a single record's current state from the API (used by the notification sync). */
export async function verifyTenderExists(id: number, signal?: AbortSignal): Promise<Tender | null> {
  try {
    return await fetchAnyTender(id, signal);
  } catch {
    return null;
  }
}

export const verificationLabels: Record<VerificationStatus, string> = {
  pending: 'Pending verification',
  verified: 'Verified',
  rejected: 'Rejected',
};
