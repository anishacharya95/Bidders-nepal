import { useCallback, useEffect, useRef, useState } from 'react';

import { errorMessage } from '@/api/client';
import { fetchAllTenders, fetchVerifiedTenders } from '@/api/tenders';
import { PAGE_STEP } from '@/config';
import { dedupeTenders, sortTenders } from '@/lib/tenders';
import type { SortKey, Tender, TenderFilters, TenderFeedStatus } from '@/types/tender';

const MAX_SERVER_PAGES = 6;

interface FeedState {
  records: Tender[];
  total: number;
  visible: number;
  pagesLoaded: number;
}

interface UseTenderFeedOptions {
  filters: TenderFilters;
  sort?: SortKey;
  endpoint?: 'all' | 'verified';
  enabled?: boolean;
}

export interface TenderFeedResult {
  items: Tender[];
  loadedRecords: number;
  total: number;
  hasMore: boolean;
  status: TenderFeedStatus;
  error: string | null;
  loading: boolean;
  refreshing: boolean;
  loadingMore: boolean;
  moreError: string | null;
  lastUpdated: string | null;
  refresh: () => void;
  loadMore: () => void;
  retry: () => void;
}

/**
 * Loads a page from the API (up to the documented 500-record maximum), sorts
 * it fully and reveals it in scroll-sized steps. This keeps sorting correct
 * across the loaded window while still fetching one request per filter change.
 */
export function useTenderFeed({
  filters,
  sort = 'newest',
  endpoint = 'all',
  enabled = true,
}: UseTenderFeedOptions): TenderFeedResult {
  const [records, setRecords] = useState<Tender[]>([]);
  const [total, setTotal] = useState(0);
  const [visible, setVisible] = useState(0);
  const [status, setStatus] = useState<TenderFeedStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [moreError, setMoreError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const sortRef = useRef(sort);
  sortRef.current = sort;
  const endpointRef = useRef(endpoint);
  endpointRef.current = endpoint;

  const stateRef = useRef<FeedState>({ records: [], total: 0, visible: 0, pagesLoaded: 0 });
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);
  const loadingMoreRef = useRef(false);

  const queryKey = JSON.stringify([
    filters.q.trim(),
    filters.category,
    filters.procurementType,
    filters.province,
    filters.district,
    filters.municipality,
    filters.organization,
    filters.ministry,
    filters.source,
    filters.status,
    filters.verificationStatus,
    filters.hasDocuments,
    sort,
    endpoint,
    enabled,
  ]);

  const requestPage = useCallback(async (page: number, force: boolean, signal: AbortSignal) => {
    const currentFilters = filtersRef.current;
    if (endpointRef.current === 'verified') {
      return fetchVerifiedTenders({
        filters: currentFilters,
        page,
        pageSize: 100,
        sort: sortRef.current,
        force,
        signal,
      });
    }
    return fetchAllTenders({
      filters: currentFilters,
      page,
      sort: sortRef.current,
      signal,
      force,
    });
  }, []);

  const load = useCallback(
    async (mode: 'initial' | 'refresh') => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;

      if (mode === 'refresh') setRefreshing(true);
      else setLoading(true);
      setError(null);
      setMoreError(null);

      try {
        const data = await requestPage(1, mode === 'refresh', controller.signal);
        if (controller.signal.aborted || requestIdRef.current !== requestId) return;
        const merged = dedupeTenders(data.items);
        const sorted = sortTenders(merged, sortRef.current);
        const nextVisible = Math.min(PAGE_STEP, sorted.length);
        stateRef.current = {
          records: sorted,
          total: data.total,
          visible: nextVisible,
          pagesLoaded: 1,
        };
        setRecords(sorted);
        setTotal(data.total);
        setVisible(nextVisible);
        setStatus('ready');
        setLastUpdated(new Date().toISOString());
      } catch (caught) {
        if (controller.signal.aborted || requestIdRef.current !== requestId) return;
        setError(errorMessage(caught));
        setStatus(stateRef.current.records.length > 0 ? 'ready' : 'error');
      } finally {
        if (requestIdRef.current === requestId) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [requestPage],
  );

  useEffect(() => {
    if (!enabled) {
      stateRef.current = { records: [], total: 0, visible: 0, pagesLoaded: 0 };
      setRecords([]);
      setTotal(0);
      setVisible(0);
      setStatus('idle');
      return;
    }
    void load('initial');
    return () => {
      abortRef.current?.abort();
    };
  }, [queryKey, enabled, load]);

  const loadMore = useCallback(async () => {
    const current = stateRef.current;
    if (loadingMoreRef.current || current.records.length === 0) return;

    if (current.visible < current.records.length) {
      const nextVisible = Math.min(current.visible + PAGE_STEP, current.records.length);
      stateRef.current = { ...current, visible: nextVisible };
      setVisible(nextVisible);
      return;
    }

    if (current.records.length >= current.total || current.pagesLoaded >= MAX_SERVER_PAGES) return;

    loadingMoreRef.current = true;
    setLoadingMore(true);
    setMoreError(null);
    const requestId = requestIdRef.current;
    try {
      const data = await requestPage(current.pagesLoaded + 1, false, new AbortController().signal);
      if (requestId !== requestIdRef.current) return;
      const merged = sortTenders(
        dedupeTenders([...current.records, ...data.items]),
        sortRef.current,
      );
      const nextVisible = Math.min(current.visible + PAGE_STEP, merged.length);
      stateRef.current = {
        records: merged,
        total: Math.max(data.total, current.total),
        visible: nextVisible,
        pagesLoaded: current.pagesLoaded + 1,
      };
      setRecords(merged);
      setTotal(Math.max(data.total, current.total));
      setVisible(nextVisible);
    } catch (caught) {
      if (requestId === requestIdRef.current) setMoreError(errorMessage(caught));
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  }, [requestPage]);

  const refresh = useCallback(() => {
    void load('refresh');
  }, [load]);

  const retry = useCallback(() => {
    void load('initial');
  }, [load]);

  const items = records.slice(0, visible);
  const hasMore =
    visible < records.length ||
    (records.length < total && stateRef.current.pagesLoaded < MAX_SERVER_PAGES);

  return {
    items,
    loadedRecords: records.length,
    total,
    hasMore,
    status,
    error,
    loading,
    refreshing,
    loadingMore,
    moreError,
    lastUpdated,
    refresh,
    loadMore,
    retry,
  };
}
