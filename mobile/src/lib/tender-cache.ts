import AsyncStorage from '@react-native-async-storage/async-storage';

import { readJson, storageKeys, writeJson } from '@/lib/storage';
import type { Tender } from '@/types/tender';

const MAX_CACHED = 30;

type TenderCache = Record<string, { at: number; tender: Tender }>;

let memoryCache: TenderCache | null = null;

async function loadCache(): Promise<TenderCache> {
  if (memoryCache) return memoryCache;
  const stored = await readJson<TenderCache>(storageKeys.tenderCache, {});
  memoryCache = stored && typeof stored === 'object' ? stored : {};
  return memoryCache;
}

/** Instantly available copy of a previously viewed tender (offline friendly). */
export async function getCachedTender(id: number): Promise<Tender | null> {
  const cache = await loadCache();
  return cache[String(id)]?.tender ?? null;
}

export async function putCachedTender(tender: Tender): Promise<void> {
  const cache = await loadCache();
  cache[String(tender.id)] = { at: Date.now(), tender };
  const entries = Object.entries(cache)
    .sort((a, b) => b[1].at - a[1].at)
    .slice(0, MAX_CACHED);
  memoryCache = Object.fromEntries(entries);
  await writeJson(storageKeys.tenderCache, memoryCache);
}

export async function recentlyViewedTenders(limit = 5): Promise<Tender[]> {
  const cache = await loadCache();
  return Object.values(cache)
    .sort((a, b) => b.at - a.at)
    .slice(0, limit)
    .map((entry) => entry.tender);
}

export async function clearTenderCache(): Promise<void> {
  memoryCache = {};
  try {
    await AsyncStorage.removeItem(storageKeys.tenderCache);
  } catch {
    // ignore
  }
}
