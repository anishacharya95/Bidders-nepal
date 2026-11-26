import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

export function EmptyState({
  icon = 'file-tray-outline',
  title,
  message,
  actionLabel,
  onAction,
}: {
  icon?: keyof typeof Ionicons.glyphMap;
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.stateWrap}>
      <View style={[styles.iconBubble, { backgroundColor: colors.navySoft }]}>
        <Ionicons name={icon} size={26} color={colors.navy} />
      </View>
      <AppText variant="h3" style={styles.center}>
        {title}
      </AppText>
      <AppText variant="small" color="textSecondary" style={[styles.center, styles.message]}>
        {message}
      </AppText>
      {actionLabel && onAction ? (
        <Button label={actionLabel} onPress={onAction} variant="secondary" size="sm" style={styles.action} />
      ) : null}
    </View>
  );
}

export function ErrorState({
  title = 'Could not load tenders',
  message,
  onRetry,
  compact = false,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const { colors } = useAppTheme();
  return (
    <Card style={[styles.errorCard, compact && styles.errorCompact]}>
      <View style={styles.errorRow}>
        <View style={[styles.iconBubble, { backgroundColor: colors.warningSoft }]}>
          <Ionicons name="cloud-offline-outline" size={22} color={colors.warning} />
        </View>
        <View style={styles.errorCopy}>
          <AppText variant="h3">{title}</AppText>
          <AppText variant="small" color="textSecondary" style={styles.message}>
            {message}
          </AppText>
        </View>
      </View>
      {onRetry ? (
        <Button
          label="Try again"
          icon="refresh"
          onPress={onRetry}
          variant="secondary"
          size="sm"
          style={styles.retry}
        />
      ) : null}
    </Card>
  );
}

export function LoadingBlock({ label = 'Loading tenders…' }: { label?: string }) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.loadingWrap}>
      <ActivityIndicator color={colors.navy} />
      <AppText variant="small" color="textSecondary">
        {label}
      </AppText>
    </View>
  );
}

export function InlineNotice({
  icon = 'information-circle-outline',
  tone = 'info',
  title,
  message,
}: {
  icon?: keyof typeof Ionicons.glyphMap;
  tone?: 'info' | 'warning' | 'success';
  title: string;
  message?: string;
}) {
  const { colors } = useAppTheme();
  const color = tone === 'warning' ? colors.warning : tone === 'success' ? colors.success : colors.info;
  const background =
    tone === 'warning' ? colors.warningSoft : tone === 'success' ? colors.successSoft : colors.infoSoft;
  return (
    <View style={[styles.notice, { backgroundColor: background, borderColor: color + '22' }]}>
      <Ionicons name={icon} size={18} color={color} />
      <View style={styles.noticeCopy}>
        <AppText variant="smallStrong" style={{ color }}>
          {title}
        </AppText>
        {message ? (
          <AppText variant="small" color="textSecondary" style={{ marginTop: 2 }}>
            {message}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  stateWrap: {
    alignItems: 'center',
    paddingVertical: spacing.xxxl,
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  iconBubble: {
    width: 52,
    height: 52,
    borderRadius: radii.lg,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.xs,
  },
  center: {
    textAlign: 'center',
  },
  message: {
    maxWidth: 300,
    textAlign: 'center',
  },
  action: {
    marginTop: spacing.md,
  },
  errorCard: {
    gap: spacing.md,
  },
  errorCompact: {
    padding: spacing.md,
  },
  errorRow: {
    flexDirection: 'row',
    gap: spacing.md,
    alignItems: 'flex-start',
  },
  errorCopy: {
    flex: 1,
    gap: 3,
  },
  retry: {
    alignSelf: 'flex-start',
  },
  loadingWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingVertical: spacing.huge,
  },
  notice: {
    flexDirection: 'row',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    alignItems: 'flex-start',
  },
  noticeCopy: {
    flex: 1,
  },
});
