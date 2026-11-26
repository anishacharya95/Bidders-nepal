import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

type StatTone = 'navy' | 'success' | 'warning' | 'info';

const tonePalette: Record<StatTone, { light: string; dark: string }> = {
  navy: { light: '#0B1F3A', dark: '#9CBBF0' },
  success: { light: '#0F7B4F', dark: '#3DD68C' },
  warning: { light: '#A96108', dark: '#F2B356' },
  info: { light: '#1D4ED8', dark: '#8AB0F8' },
};

interface StatCardProps {
  label: string;
  value: number | string;
  hint?: string;
  icon: keyof typeof Ionicons.glyphMap;
  tone?: StatTone;
  loading?: boolean;
}

export function StatCard({ label, value, hint, icon, tone = 'navy', loading }: StatCardProps) {
  const { colors, isDark, shadow } = useAppTheme();
  const tint = tonePalette[tone][isDark ? 'dark' : 'light'];

  return (
    <View
      style={[
        styles.card,
        { backgroundColor: colors.surface, borderColor: colors.border },
        shadow('sm'),
      ]}>
      <View style={styles.topRow}>
        <View style={[styles.iconBubble, { backgroundColor: tint + (isDark ? '26' : '14') }]}>
          <Ionicons name={icon} size={16} color={tint} />
        </View>
        {loading ? <Skeleton width={26} height={8} /> : null}
      </View>
      {loading ? (
        <Skeleton width={54} height={24} style={{ marginTop: 6 }} />
      ) : (
        <AppText variant="display" style={styles.value}>
          {typeof value === 'number' ? value.toLocaleString('en-US') : value}
        </AppText>
      )}
      <AppText variant="smallStrong" color="textSecondary" numberOfLines={1}>
        {label}
      </AppText>
      {hint ? (
        <AppText variant="caption" color="textTertiary" numberOfLines={2} style={styles.hint}>
          {hint}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    minWidth: 150,
    borderRadius: radii.lg,
    borderWidth: 1,
    padding: spacing.md + 2,
    gap: 2,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  iconBubble: {
    width: 30,
    height: 30,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  value: {
    fontSize: 27,
    lineHeight: 33,
  },
  hint: {
    marginTop: 3,
  },
});
