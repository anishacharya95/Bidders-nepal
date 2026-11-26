import { Platform, TextStyle, ViewStyle } from 'react-native';

export type ThemeMode = 'system' | 'light' | 'dark';

export type ThemeColors = {
  background: string;
  backgroundAlt: string;
  surface: string;
  surfaceMuted: string;
  surfaceElevated: string;
  border: string;
  borderStrong: string;
  text: string;
  textSecondary: string;
  textTertiary: string;
  navy: string;
  navyDeep: string;
  navySoft: string;
  onNavy: string;
  primary: string;
  onPrimary: string;
  success: string;
  successSoft: string;
  warning: string;
  warningSoft: string;
  danger: string;
  dangerSoft: string;
  info: string;
  infoSoft: string;
  overlay: string;
  shadow: string;
  heroFrom: string;
  heroTo: string;
  skeleton: string;
};

const light: ThemeColors = {
  background: '#F6F7FA',
  backgroundAlt: '#EEF1F6',
  surface: '#FFFFFF',
  surfaceMuted: '#F2F5F9',
  surfaceElevated: '#FFFFFF',
  border: '#E4E8F0',
  borderStrong: '#D2DAE6',
  text: '#0A1526',
  textSecondary: '#5A6779',
  textTertiary: '#8B96A8',
  navy: '#0B1F3A',
  navyDeep: '#071427',
  navySoft: '#E9EEF6',
  onNavy: '#FFFFFF',
  primary: '#0B1F3A',
  onPrimary: '#FFFFFF',
  success: '#0F7B4F',
  successSoft: '#E6F5EC',
  warning: '#A96108',
  warningSoft: '#FCF1DF',
  danger: '#B42318',
  dangerSoft: '#FDECEA',
  info: '#1D4ED8',
  infoSoft: '#EAF0FF',
  overlay: 'rgba(8,17,31,0.45)',
  shadow: 'rgba(11,31,58,0.10)',
  heroFrom: '#0B1F3A',
  heroTo: '#16375F',
  skeleton: '#E9EDF3',
};

const dark: ThemeColors = {
  background: '#070C14',
  backgroundAlt: '#0B1220',
  surface: '#101A29',
  surfaceMuted: '#162233',
  surfaceElevated: '#152033',
  border: '#1E2B3F',
  borderStrong: '#2B3B53',
  text: '#F2F5FA',
  textSecondary: '#9BA8BC',
  textTertiary: '#75849A',
  navy: '#B8CDEB',
  navyDeep: '#050B14',
  navySoft: '#16253A',
  onNavy: '#FFFFFF',
  primary: '#3B7BE0',
  onPrimary: '#FFFFFF',
  success: '#3DD68C',
  successSoft: '#0E2A20',
  warning: '#F2B356',
  warningSoft: '#2A2214',
  danger: '#F87171',
  dangerSoft: '#2A1618',
  info: '#8AB0F8',
  infoSoft: '#152238',
  overlay: 'rgba(2,6,12,0.62)',
  shadow: 'rgba(0,0,0,0.35)',
  heroFrom: '#08182C',
  heroTo: '#122A47',
  skeleton: '#1A2537',
};

export const palettes = { light, dark } as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  huge: 40,
} as const;

export const radii = {
  sm: 10,
  md: 14,
  lg: 18,
  xl: 24,
  xxl: 28,
  pill: 999,
} as const;

export const fonts = {
  regular: 'PlusJakartaSans_400Regular',
  medium: 'PlusJakartaSans_500Medium',
  semibold: 'PlusJakartaSans_600SemiBold',
  bold: 'PlusJakartaSans_700Bold',
  extrabold: 'PlusJakartaSans_800ExtraBold',
} as const;

export const maxContentWidth = 720;

/** Bottom padding that keeps scroll content above the floating tab bar. */
export const tabBarSpace = 108;

export function shadowStyle(colors: ThemeColors, level: 'sm' | 'md' | 'lg' = 'md'): ViewStyle {
  if (Platform.OS === 'android') {
    return { elevation: level === 'sm' ? 2 : level === 'md' ? 4 : 8, shadowColor: colors.shadow };
  }
  const config = {
    sm: { radius: 8, opacity: 1, offset: { width: 0, height: 2 } },
    md: { radius: 18, opacity: 1, offset: { width: 0, height: 8 } },
    lg: { radius: 28, opacity: 1, offset: { width: 0, height: 16 } },
  }[level];
  return {
    shadowColor: colors.shadow,
    shadowOpacity: config.opacity,
    shadowRadius: config.radius,
    shadowOffset: config.offset,
  };
}

export type TextVariant =
  | 'display'
  | 'h1'
  | 'h2'
  | 'h3'
  | 'body'
  | 'bodyStrong'
  | 'small'
  | 'smallStrong'
  | 'caption'
  | 'label'
  | 'button';

export const textVariants: Record<TextVariant, TextStyle> = {
  display: { fontFamily: fonts.extrabold, fontSize: 30, lineHeight: 37, letterSpacing: -0.8 },
  h1: { fontFamily: fonts.bold, fontSize: 24, lineHeight: 31, letterSpacing: -0.5 },
  h2: { fontFamily: fonts.bold, fontSize: 19, lineHeight: 26, letterSpacing: -0.3 },
  h3: { fontFamily: fonts.semibold, fontSize: 16, lineHeight: 23, letterSpacing: -0.1 },
  body: { fontFamily: fonts.regular, fontSize: 14.5, lineHeight: 22 },
  bodyStrong: { fontFamily: fonts.medium, fontSize: 14.5, lineHeight: 22 },
  small: { fontFamily: fonts.regular, fontSize: 13, lineHeight: 19 },
  smallStrong: { fontFamily: fonts.semibold, fontSize: 13, lineHeight: 19 },
  caption: { fontFamily: fonts.medium, fontSize: 11.5, lineHeight: 16 },
  label: {
    fontFamily: fonts.semibold,
    fontSize: 11.5,
    lineHeight: 16,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  button: { fontFamily: fonts.semibold, fontSize: 14.5, lineHeight: 20 },
};
