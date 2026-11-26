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

import { readJson, storageKeys, writeJson } from '@/lib/storage';
import type { Tender } from '@/types/tender';

interface SavedContextValue {
  saved: Tender[];
  savedIds: Set<number>;
  hydrated: boolean;
  isSaved: (id: number) => boolean;
  toggleSaved: (tender: Tender) => boolean;
  removeSaved: (id: number) => void;
  clearSaved: () => void;
}

const SavedContext = createContext<SavedContextValue | null>(null);

export function SavedProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<Tender[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const hydratedRef = useRef(false);

  useEffect(() => {
    let active = true;
    readJson<Tender[]>(storageKeys.savedTenders, []).then((stored) => {
      if (!active) return;
      setSaved(Array.isArray(stored) ? stored.filter((item) => item && typeof item.id === 'number') : []);
      hydratedRef.current = true;
      setHydrated(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    void writeJson(storageKeys.savedTenders, saved);
  }, [saved]);

  const savedIds = useMemo(() => new Set(saved.map((item) => item.id)), [saved]);

  const toggleSaved = useCallback((tender: Tender) => {
    let nowSaved = false;
    setSaved((current) => {
      const exists = current.some((item) => item.id === tender.id);
      if (exists) return current.filter((item) => item.id !== tender.id);
      nowSaved = true;
      return [tender, ...current];
    });
    return nowSaved;
  }, []);

  const removeSaved = useCallback((id: number) => {
    setSaved((current) => current.filter((item) => item.id !== id));
  }, []);

  const clearSaved = useCallback(() => setSaved([]), []);

  const value = useMemo<SavedContextValue>(
    () => ({
      saved,
      savedIds,
      hydrated,
      isSaved: (id: number) => savedIds.has(id),
      toggleSaved,
      removeSaved,
      clearSaved,
    }),
    [clearSaved, hydrated, removeSaved, saved, savedIds, toggleSaved],
  );

  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>;
}

export function useSavedTenders(): SavedContextValue {
  const context = useContext(SavedContext);
  if (!context) throw new Error('useSavedTenders must be used inside SavedProvider');
  return context;
}
