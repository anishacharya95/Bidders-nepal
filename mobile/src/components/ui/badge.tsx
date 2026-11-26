import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

export type BadgeTone = 'success' | 'warning' | 'danger' | 'neutral' | 'navy' | 'info';

interface BadgeProps {
  label: string;
  tone?: BadgeTone;
  icon?: keyof typeof Ionicons.glyphMap;
  dot?: boolean;
  size?: 'sm' | 'md';
}

export function Badge({ label, tone = 'neutral', icon, dot = false, size = 'sm' }: BadgeProps) {
  const { colors } = useAppTheme();

  const palette: Record<BadgeTone, { bg: string; fg: string }> = {
    success: { bg: colors.successSoft, fg: colors.success },
    warning: { bg: colors.warningSoft, fg: colors.warning },
    danger: { bg: colors.dangerSoft, fg: colors.danger },
    neutral: { bg: colors.surfaceMuted, fg: colors.textSecondary },
    navy: { bg: colors.navySoft, fg: colors.navy },
    info: { bg: colors.infoSoft, fg: colors.info },
  };
  const { bg, fg } = palette[tone];

  return (
    <View
      style={[
        styles.badge,
        { backgroundColor: bg },
        size === 'md' && styles.badgeMd,
      ]}>
      {dot ? <View style={[styles.dot, { backgroundColor: fg }]} /> : null}
      {icon ? <Ionicons name={icon} size={size === 'md' ? 13 : 11} color={fg} /> : null}
      <AppText
        variant={size === 'md' ? 'caption' : 'caption'}
        style={[styles.label, { color: fg, fontSize: size === 'md' ? 12 : 11 }]}
        numberOfLines={1}>
        {label}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: radii.pill,
    alignSelf: 'flex-start',
  },
  badgeMd: {
    paddingHorizontal: 11,
    paddingVertical: 6,
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: 3,
  },
  label: {
    letterSpacing: 0.1,
  },
});
