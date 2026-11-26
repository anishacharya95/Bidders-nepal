import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, Pressable, StyleSheet, View, type ViewStyle } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps {
  label: string;
  onPress?: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  rightIcon?: keyof typeof Ionicons.glyphMap;
  variant?: ButtonVariant;
  loading?: boolean;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  style?: ViewStyle;
}

export function Button({
  label,
  onPress,
  icon,
  rightIcon,
  variant = 'primary',
  loading = false,
  disabled = false,
  size = 'md',
  style,
}: ButtonProps) {
  const { colors } = useAppTheme();

  const backgrounds: Record<ButtonVariant, string> = {
    primary: colors.primary,
    secondary: colors.surface,
    ghost: 'transparent',
    danger: colors.dangerSoft,
  };
  const foregrounds: Record<ButtonVariant, string> = {
    primary: colors.onPrimary,
    secondary: colors.text,
    ghost: colors.textSecondary,
    danger: colors.danger,
  };
  const borderColors: Record<ButtonVariant, string> = {
    primary: colors.primary,
    secondary: colors.border,
    ghost: 'transparent',
    danger: colors.dangerSoft,
  };
  const height = size === 'lg' ? 52 : size === 'sm' ? 36 : 46;
  const fg = foregrounds[variant];

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor: backgrounds[variant],
          borderColor: borderColors[variant],
          height,
          opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
        },
        style,
      ]}>
      {loading ? (
        <ActivityIndicator size="small" color={fg} />
      ) : (
        <View style={styles.content}>
          {icon ? <Ionicons name={icon} size={size === 'sm' ? 14 : 17} color={fg} /> : null}
          <AppText
            variant="button"
            style={{ color: fg, fontSize: size === 'sm' ? 13 : 14.5 }}
            numberOfLines={1}>
            {label}
          </AppText>
          {rightIcon ? (
            <Ionicons name={rightIcon} size={size === 'sm' ? 14 : 17} color={fg} />
          ) : null}
        </View>
      )}
    </Pressable>
  );
}

interface IconButtonProps {
  icon: keyof typeof Ionicons.glyphMap;
  onPress?: () => void;
  variant?: 'surface' | 'navy' | 'ghost' | 'glass';
  size?: number;
  color?: string;
  accessibilityLabel?: string;
  active?: boolean;
}

export function IconButton({
  icon,
  onPress,
  variant = 'surface',
  size = 40,
  color,
  accessibilityLabel,
  active,
}: IconButtonProps) {
  const { colors } = useAppTheme();
  const background =
    variant === 'navy'
      ? colors.primary
      : variant === 'glass'
        ? 'rgba(255,255,255,0.16)'
        : variant === 'ghost'
          ? 'transparent'
          : colors.surfaceMuted;
  const tint =
    color ??
    (variant === 'navy' ? colors.onPrimary : variant === 'glass' ? '#FFFFFF' : colors.text);

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      hitSlop={6}
      style={({ pressed }) => [
        styles.iconButton,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: background,
          borderColor: variant === 'surface' ? colors.border : 'transparent',
          borderWidth: variant === 'surface' ? 1 : 0,
          opacity: pressed ? 0.7 : 1,
        },
      ]}>
      <Ionicons name={icon} size={size * 0.46} color={active ? colors.success : tint} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: radii.md,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  iconButton: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});
