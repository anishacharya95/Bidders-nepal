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

const MAX_RECENT_SEARCHES = 8;
const MAX_TERM_LENGTH = 80;

interface SearchHistoryContextValue {
  terms: string[];
  addTerm: (term: string) => void;
  removeTerm: (term: string) => void;
  clearTerms: () => void;
}

const SearchHistoryContext = createContext<SearchHistoryContextValue | null>(null);

export function SearchHistoryProvider({ children }: { children: ReactNode }) {
  const [terms, setTerms] = useState<string[]>([]);
  const hydratedRef = useRef(false);

  useEffect(() => {
    let active = true;
    readJson<string[]>(storageKeys.recentSearches, []).then((stored) => {
      if (!active) return;
      setTerms(Array.isArray(stored) ? stored.filter((term) => typeof term === 'string') : []);
      hydratedRef.current = true;
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    void writeJson(storageKeys.recentSearches, terms);
  }, [terms]);

  const addTerm = useCallback((raw: string) => {
    const term = raw.trim().slice(0, MAX_TERM_LENGTH);
    if (term.length < 2) return;
    setTerms((current) => [
      term,
      ...current.filter((item) => item.toLowerCase() !== term.toLowerCase()),
    ].slice(0, MAX_RECENT_SEARCHES));
  }, []);

  const removeTerm = useCallback((term: string) => {
    setTerms((current) => current.filter((item) => item !== term));
  }, []);

  const clearTerms = useCallback(() => setTerms([]), []);

  const value = useMemo<SearchHistoryContextValue>(
    () => ({ terms, addTerm, removeTerm, clearTerms }),
    [addTerm, clearTerms, removeTerm, terms],
  );

  return (
    <SearchHistoryContext.Provider value={value}>{children}</SearchHistoryContext.Provider>
  );
}

export function useSearchHistory(): SearchHistoryContextValue {
  const context = useContext(SearchHistoryContext);
  if (!context) throw new Error('useSearchHistory must be used inside SearchHistoryProvider');
  return context;
}
