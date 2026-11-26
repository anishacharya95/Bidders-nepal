import AsyncStorage from '@react-native-async-storage/async-storage';

export const storageKeys = {
  themeMode: 'bn.themeMode',
  savedTenders: 'bn.savedTenders',
  recentSearches: 'bn.recentSearches',
  notificationPrefs: 'bn.notificationPrefs',
  notificationFeed: 'bn.notificationFeed',
  notificationBaseline: 'bn.notificationBaseline',
  tenderCache: 'bn.tenderCache',
} as const;

export async function readJson<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function writeJson(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage failures must never break the UI.
  }
}

export async function removeKey(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key);
  } catch {
    // ignore
  }
}
