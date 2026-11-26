import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { CLOSING_SOON_ALERT_DAYS } from '@/config';
import { daysUntil } from '@/lib/format';
import { readJson, storageKeys, writeJson } from '@/lib/storage';
import { documentsFor, isClosingSoon } from '@/lib/tenders';
import type { Tender } from '@/types/tender';

export type NotificationType = 'new' | 'closing' | 'deadline' | 'document' | 'amendment';

export interface AppNotification {
  id: string;
  type: NotificationType;
  tenderId: number;
  tenderTitle: string;
  message: string;
  createdAt: string;
  read: boolean;
}

export interface NotificationPrefs {
  newTenders: boolean;
  closingSoon: boolean;
  deadlineChanges: boolean;
  newDocuments: boolean;
  amendments: boolean;
}

export const DEFAULT_NOTIFICATION_PREFS: NotificationPrefs = {
  newTenders: true,
  closingSoon: true,
  deadlineChanges: true,
  newDocuments: true,
  amendments: true,
};

interface BaselineEntry {
  deadline: string | null;
  documentCount: number;
  updatedAt: string;
  status: string;
  closingFlagged: boolean;
}

interface Baseline {
  capturedAt: string;
  entries: Record<string, BaselineEntry>;
}

interface FeedState {
  items: AppNotification[];
  lastSync: string | null;
}

export interface SyncResult {
  baselineCreated: boolean;
  created: number;
  checked: number;
}

interface NotificationContextValue {
  items: AppNotification[];
  unreadCount: number;
  prefs: NotificationPrefs;
  lastSync: string | null;
  syncing: boolean;
  syncError: string | null;
  hydrated: boolean;
  setPref: (key: keyof NotificationPrefs, value: boolean) => void;
  syncFromTenders: (tenders: Tender[]) => Promise<SyncResult>;
  markAllRead: () => void;
  markRead: (id: string) => void;
  clearAll: () => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

const MAX_NOTIFICATIONS = 120;

function baselineFrom(tenders: Tender[]): Baseline {
  const entries: Record<string, BaselineEntry> = {};
  for (const tender of tenders) {
    entries[String(tender.id)] = {
      deadline: tender.deadline ?? null,
      documentCount: documentsFor(tender).length,
      updatedAt: tender.updated_at,
      status: tender.status,
      closingFlagged: isClosingSoon(tender, CLOSING_SOON_ALERT_DAYS),
    };
  }
  return { capturedAt: new Date().toISOString(), entries };
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<NotificationPrefs>(DEFAULT_NOTIFICATION_PREFS);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const baselineRef = useRef<Baseline | null>(null);
  const prefsRef = useRef<NotificationPrefs>(DEFAULT_NOTIFICATION_PREFS);
  const itemsRef = useRef<AppNotification[]>([]);
  const hydratedRef = useRef(false);
  const syncingRef = useRef(false);

  useEffect(() => {
    let active = true;
    Promise.all([
      readJson<FeedState>(storageKeys.notificationFeed, { items: [], lastSync: null }),
      readJson<NotificationPrefs>(storageKeys.notificationPrefs, DEFAULT_NOTIFICATION_PREFS),
      readJson<Baseline | null>(storageKeys.notificationBaseline, null),
    ]).then(([feed, storedPrefs, storedBaseline]) => {
      if (!active) return;
      const feedItems = Array.isArray(feed?.items) ? feed.items : [];
      setItems(feedItems);
      itemsRef.current = feedItems;
      setLastSync(feed?.lastSync ?? null);
      const mergedPrefs = { ...DEFAULT_NOTIFICATION_PREFS, ...(storedPrefs ?? {}) };
      setPrefs(mergedPrefs);
      prefsRef.current = mergedPrefs;
      if (storedBaseline && storedBaseline.entries) {
        setBaseline(storedBaseline);
        baselineRef.current = storedBaseline;
      }
      hydratedRef.current = true;
      setHydrated(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    void writeJson(storageKeys.notificationFeed, { items, lastSync } satisfies FeedState);
  }, [items, lastSync]);

  useEffect(() => {
    if (!hydratedRef.current) return;
    void writeJson(storageKeys.notificationPrefs, prefs);
  }, [prefs]);

  const setPref = useCallback((key: keyof NotificationPrefs, value: boolean) => {
    setPrefs((current) => {
      const next = { ...current, [key]: value };
      prefsRef.current = next;
      return next;
    });
  }, []);

  /**
   * Compare the live API feed with the previous snapshot. Notifications are
   * only created for real, observed changes — never for invented events.
   * The first run only records a baseline.
   */
  const syncFromTenders = useCallback(async (tenders: Tender[]): Promise<SyncResult> => {
    if (syncingRef.current) return { baselineCreated: false, created: 0, checked: 0 };
    syncingRef.current = true;
    setSyncing(true);
    setSyncError(null);
    try {
      if (!Array.isArray(tenders) || tenders.length === 0) {
        throw new Error('No tenders available to compare yet.');
      }
      const now = new Date();
      const nowIso = now.toISOString();
      const current = prefsRef.current;
      const previous = baselineRef.current;
      const nextEntries: Record<string, BaselineEntry> = {};
      const created: AppNotification[] = [];

      const push = (
        type: NotificationType,
        tender: Tender,
        message: string,
      ) => {
        created.push({
          id: `${type}-${tender.id}-${nowIso}`,
          type,
          tenderId: tender.id,
          tenderTitle: tender.title,
          message,
          createdAt: nowIso,
          read: false,
        });
      };

      const isFirstBaseline = !previous || Object.keys(previous.entries ?? {}).length === 0;

      for (const tender of tenders) {
        const entry = previous?.entries?.[String(tender.id)];
        const docCount = documentsFor(tender).length;
        const closing = isClosingSoon(tender, CLOSING_SOON_ALERT_DAYS);

        if (!isFirstBaseline && entry) {
          if (current.deadlineChanges && (tender.deadline ?? null) !== entry.deadline) {
            push(
              'deadline',
              tender,
              entry.deadline
                ? `Deadline changed from ${entry.deadline.slice(0, 10)} to ${
                    tender.deadline ? tender.deadline.slice(0, 10) : 'not published'
                  }.`
                : 'A submission deadline was published for this tender.',
            );
          }
          if (current.newDocuments && docCount > entry.documentCount) {
            push(
              'document',
              tender,
              docCount === 1
                ? 'A bid document is now available for this tender.'
                : `${docCount - entry.documentCount} new bid document(s) are now available.`,
            );
          }
          if (current.amendments && tender.status !== entry.status) {
            push('amendment', tender, `Tender status changed to ${tender.status}.`);
          } else if (
            current.amendments &&
            tender.updated_at !== entry.updatedAt &&
            (tender.deadline ?? null) === entry.deadline &&
            docCount === entry.documentCount &&
            tender.status === entry.status
          ) {
            push('amendment', tender, 'Tender details were updated by the source.');
          }
          if (current.closingSoon && closing && !entry.closingFlagged) {
            const days = daysUntil(tender.deadline);
            push(
              'closing',
              tender,
              days === 0
                ? 'Submission closes today.'
                : `Submission closes in ${days} day${days === 1 ? '' : 's'}.`,
            );
          }
        } else if (!isFirstBaseline && !entry && current.newTenders) {
          push('new', tender, 'A new notice appeared in the public API feed.');
        }

        nextEntries[String(tender.id)] = {
          deadline: tender.deadline ?? null,
          documentCount: docCount,
          updatedAt: tender.updated_at,
          status: tender.status,
          closingFlagged: closing,
        };
      }

      const nextBaseline: Baseline = {
        capturedAt: nowIso,
        entries: nextEntries,
      };
      baselineRef.current = nextBaseline;
      setBaseline(nextBaseline);
      await writeJson(storageKeys.notificationBaseline, nextBaseline);

      if (created.length > 0) {
        const merged = [...created, ...itemsRef.current].slice(0, MAX_NOTIFICATIONS);
        itemsRef.current = merged;
        setItems(merged);
      }
      setLastSync(nowIso);

      if (isFirstBaseline) {
        return { baselineCreated: true, created: 0, checked: tenders.length };
      }
      return { baselineCreated: false, created: created.length, checked: tenders.length };
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : 'Could not check for updates.');
      throw error;
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, []);

  const markAllRead = useCallback(() => {
    setItems((current) => {
      const next = current.map((item) => (item.read ? item : { ...item, read: true }));
      itemsRef.current = next;
      return next;
    });
  }, []);

  const markRead = useCallback((id: string) => {
    setItems((current) => {
      const next = current.map((item) => (item.id === id ? { ...item, read: true } : item));
      itemsRef.current = next;
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setItems([]);
    itemsRef.current = [];
  }, []);

  const unreadCount = useMemo(() => items.filter((item) => !item.read).length, [items]);

  const value = useMemo<NotificationContextValue>(
    () => ({
      items,
      unreadCount,
      prefs,
      lastSync,
      syncing,
      syncError,
      hydrated,
      setPref,
      syncFromTenders,
      markAllRead,
      markRead,
      clearAll,
    }),
    [
      clearAll,
      hydrated,
      items,
      lastSync,
      markAllRead,
      markRead,
      prefs,
      setPref,
      syncError,
      syncFromTenders,
      syncing,
      unreadCount,
    ],
  );

  void baseline;

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotifications(): NotificationContextValue {
  const context = useContext(NotificationContext);
  if (!context) throw new Error('useNotifications must be used inside NotificationProvider');
  return context;
}
