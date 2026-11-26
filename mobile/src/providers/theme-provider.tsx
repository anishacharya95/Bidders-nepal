import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useColorScheme as useSystemColorScheme } from 'react-native';

import { readJson, storageKeys, writeJson } from '@/lib/storage';
import { palettes, shadowStyle, type ThemeColors, type ThemeMode } from '@/theme';

interface ThemeContextValue {
  mode: ThemeMode;
  isDark: boolean;
  colors: ThemeColors;
  setMode: (mode: ThemeMode) => void;
  cycleMode: () => void;
  shadow: (level?: 'sm' | 'md' | 'lg') => ReturnType<typeof shadowStyle>;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const systemScheme = useSystemColorScheme();
  const [mode, setModeState] = useState<ThemeMode>('system');
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let active = true;
    readJson<ThemeMode>(storageKeys.themeMode, 'system').then((stored) => {
      if (!active) return;
      if (stored === 'light' || stored === 'dark' || stored === 'system') setModeState(stored);
      setHydrated(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    void writeJson(storageKeys.themeMode, next);
  }, []);

  const resolved = mode === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : mode;
  const isDark = resolved === 'dark';
  const colors = palettes[isDark ? 'dark' : 'light'];

  const cycleMode = useCallback(() => {
    setMode(mode === 'system' ? 'light' : mode === 'light' ? 'dark' : 'system');
  }, [mode, setMode]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      isDark,
      colors,
      setMode,
      cycleMode,
      shadow: (level = 'md') => shadowStyle(colors, level),
    }),
    [colors, cycleMode, isDark, mode, setMode],
  );

  // `hydrated` is not exposed: the theme simply settles once storage reads.
  void hydrated;

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useAppTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useAppTheme must be used inside AppThemeProvider');
  return context;
}
