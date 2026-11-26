import { StyleSheet, Text, type TextProps } from 'react-native';

import { useAppTheme } from '@/providers/theme-provider';
import { textVariants, type TextVariant, type ThemeColors } from '@/theme';

export type AppTextColor = keyof Pick<
  ThemeColors,
  | 'text'
  | 'textSecondary'
  | 'textTertiary'
  | 'onNavy'
  | 'onPrimary'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'primary'
  | 'navy'
>;

interface AppTextProps extends TextProps {
  variant?: TextVariant;
  color?: AppTextColor;
}

export function AppText({ variant = 'body', color = 'text', style, ...rest }: AppTextProps) {
  const { colors } = useAppTheme();
  return <Text style={[textVariants[variant], { color: colors[color] }, style]} {...rest} />;
}

export const textStyles = StyleSheet.create({
  flexible: { flexShrink: 1 },
});
