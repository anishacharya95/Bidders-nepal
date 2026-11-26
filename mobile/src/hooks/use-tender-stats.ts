import { useCallback, useEffect, useRef, useState } from 'react';

import { errorMessage } from '@/api/client';
import { fetchAllTenders } from '@/api/tenders';
import { CACHE_TTL_MS, MAX_PAGE_SIZE } from '@/config';
import { isClosingSoon } from '@/lib/tenders';
import { deriveFacets, sortTenders, type Facet } from '@/lib/tenders';
import { EMPTY_FILTERS, type Tender } from '@/types/tender';

interface StatsSnapshot {
  total: number;
  open: number;
  verified: number;
  pending: number;
  closingSoon: number;
  categories: Facet[];
  provinces: Facet[];
  sources: Facet[];
  recent: Tender[];
  loadedCount: number;
  updatedAt: string;
  openEstimated: boolean;
}

interface StatsState extends StatsSnapshot {
  loading: boolean;
  refreshing: boolean;
  error: string | null;
}

const initialState: StatsState = {
  total: 0,
  open: 0,
  verified: 0,
  pending: 0,
  closingSoon: 0,
  categories: [],
  provinces: [],
  sources: [],
  recent: [],
  loadedCount: 0,
  updatedAt: '',
  openEstimated: false,
  loading: true,
  refreshing: false,
  error: null,
};

let cachedSnapshot: { at: number; value: StatsSnapshot } | null = null;

/**
 * Dashboard statistics come from the API's own `total` counters. Values that
 * the API cannot aggregate (closing soon, category mix) are computed from the
 * latest loaded window and labelled as such in the UI.
 */
export function useTenderStats() {
  const [state, setState] = useState<StatsState>(() =>
    cachedSnapshot && Date.now() - cachedSnapshot.at < CACHE_TTL_MS
      ? { ...cachedSnapshot.value, loading: false, refreshing: false, error: null }
      : initialState,
  );
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    setState((current) => ({
      ...current,
      loading: mode === 'initial' && current.loadedCount === 0,
      refreshing: mode === 'refresh',
      error: null,
    }));

    try {
      const force = mode === 'refresh';
      const [windowResult, openResult, verifiedResult, pendingResult] = await Promise.allSettled([
        fetchAllTenders({ filters: EMPTY_FILTERS, page: 1, pageSize: MAX_PAGE_SIZE, force }),
        fetchAllTenders({
          filters: { ...EMPTY_FILTERS, status: 'open' },
          page: 1,
          pageSize: 1,
          force,
        }),
        fetchAllTenders({
          filters: { ...EMPTY_FILTERS, verificationStatus: 'verified' },
          page: 1,
          pageSize: 1,
          force,
        }),
        fetchAllTenders({
          filters: { ...EMPTY_FILTERS, verificationStatus: 'pending' },
          page: 1,
          pageSize: 1,
          force,
        }),
      ]);

      if (windowResult.status !== 'fulfilled') throw windowResult.reason;

      const window = windowResult.value;
      const facets = deriveFacets(window.items);
      const verifiedInWindow = window.items.filter(
        (item) => item.verification_status?.toLowerCase() === 'verified',
      ).length;

      const snapshot: StatsSnapshot = {
        total: window.total,
        open:
          openResult.status === 'fulfilled'
            ? openResult.value.total
            : window.items.filter((item) => item.status?.toLowerCase() === 'open').length,
        openEstimated: openResult.status !== 'fulfilled',
        verified:
          verifiedResult.status === 'fulfilled'
            ? verifiedResult.value.total
            : verifiedInWindow,
        pending:
          pendingResult.status === 'fulfilled'
            ? pendingResult.value.total
            : Math.max(window.total - verifiedInWindow, 0),
        closingSoon: window.items.filter((item) => isClosingSoon(item)).length,
        categories: facets.categories,
        provinces: facets.provinces,
        sources: facets.sources,
        recent: sortTenders(window.items, 'newest').slice(0, 6),
        loadedCount: window.items.length,
        updatedAt: new Date().toISOString(),
      };

      cachedSnapshot = { at: Date.now(), value: snapshot };
      if (!mountedRef.current) return;
      setState({ ...snapshot, loading: false, refreshing: false, error: null });
    } catch (caught) {
      if (!mountedRef.current) return;
      setState((current) => ({
        ...current,
        loading: false,
        refreshing: false,
        error: errorMessage(caught),
      }));
    }
  }, []);

  useEffect(() => {
    if (cachedSnapshot && Date.now() - cachedSnapshot.at < CACHE_TTL_MS) return;
    void load('initial');
  }, [load]);

  const refresh = useCallback(() => {
    void load('refresh');
  }, [load]);

  return { ...state, refresh };
}
