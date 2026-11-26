import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { memo } from 'react';
import { Platform, Pressable, StyleSheet, View, type ViewStyle } from 'react-native';

import { Badge, type BadgeTone } from '@/components/ui/badge';
import { AppText } from '@/components/ui/app-text';
import { formatDate, relativeTime, remainingLabel } from '@/lib/format';
import {
  documentsFor,
  isOpenTender,
  isVerified,
  organisationDisplayName,
  statusLabel,
  verificationLabel,
} from '@/lib/tenders';
import { useAppTheme } from '@/providers/theme-provider';
import { useSavedTenders } from '@/providers/saved-provider';
import { fonts, radii, spacing } from '@/theme';
import type { Tender } from '@/types/tender';

interface TenderCardProps {
  tender: Tender;
  onPress: () => void;
  compact?: boolean;
  style?: ViewStyle;
}

const organisationName = organisationDisplayName;

function locationLabel(tender: Tender): string | null {
  const parts = [tender.district, tender.province].filter(
    (value): value is string => !!value && value.trim().length > 0,
  );
  return parts.length > 0 ? parts.join(', ') : null;
}

const remainingToneToBadge: Record<string, BadgeTone> = {
  success: 'success',
  warning: 'warning',
  danger: 'danger',
  neutral: 'neutral',
};

export const TenderCard = memo(function TenderCard({
  tender,
  onPress,
  compact = false,
  style,
}: TenderCardProps) {
  const { colors, isDark, shadow } = useAppTheme();
  const { isSaved, toggleSaved } = useSavedTenders();

  const saved = isSaved(tender.id);
  const documents = documentsFor(tender);
  const open = isOpenTender(tender);
  const verified = isVerified(tender);
  const remaining = remainingLabel(tender.deadline);
  const location = locationLabel(tender);
  const published = formatDate(tender.published_date);
  const added = relativeTime(tender.created_at);

  const onSave = () => {
    const nowSaved = toggleSaved(tender);
    if (Platform.OS !== 'web') {
      void Haptics.notificationAsync(
        nowSaved
          ? Haptics.NotificationFeedbackType.Success
          : Haptics.NotificationFeedbackType.Warning,
      );
    }
  };

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${tender.title}, ${organisationName(tender)}`}
      style={({ pressed }) => [
        styles.card,
        {
          backgroundColor: colors.surface,
          borderColor: colors.border,
          width: compact ? 272 : '100%',
        },
        shadow('sm'),
        pressed && styles.pressed,
        style,
      ]}>
      <View style={styles.topRow}>
        <View style={[styles.categoryPill, { backgroundColor: isDark ? colors.navySoft : colors.navySoft }]}>
          <Ionicons name="pricetag-outline" size={10} color={colors.navy} />
          <AppText variant="caption" style={[styles.categoryText, { color: colors.navy }]}>
            {tender.category || 'Other'}
          </AppText>
        </View>
        <View style={styles.topBadges}>
          <Badge
            label={statusLabel(tender.status)}
            tone={open ? 'success' : 'neutral'}
            dot
            icon={open ? undefined : 'lock-closed'}
          />
          <Pressable
            onPress={onSave}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel={saved ? 'Remove from saved' : 'Save tender'}
            style={({ pressed }) => [styles.bookmark, pressed && { opacity: 0.6 }]}>
            <Ionicons
              name={saved ? 'bookmark' : 'bookmark-outline'}
              size={18}
              color={saved ? colors.navy : colors.textTertiary}
            />
          </Pressable>
        </View>
      </View>

      <AppText variant="h3" numberOfLines={compact ? 2 : 3} style={styles.title}>
        {tender.title}
      </AppText>

      <View style={styles.orgRow}>
        <Ionicons name="business-outline" size={13} color={colors.textTertiary} />
        <AppText variant="small" color="textSecondary" numberOfLines={1} style={styles.flex}>
          {organisationName(tender)}
        </AppText>
      </View>

      {!compact ? (
        <View style={styles.metaGrid}>
          {tender.notice_number ? (
            <MetaItem icon="barcode-outline" text={tender.notice_number} />
          ) : null}
          <MetaItem
            icon="location-outline"
            text={location ?? 'Location not published'}
            muted={!location}
          />
          <MetaItem
            icon="calendar-outline"
            text={published ? `Published ${published}` : `Added ${added ?? 'recently'}`}
          />
          <MetaItem
            icon="alarm-outline"
            text={formatDate(tender.deadline) ?? 'Deadline not published'}
            muted={!tender.deadline}
          />
        </View>
      ) : null}

      <View style={styles.badgesRow}>
        <Badge
          label={remaining.label}
          tone={remainingToneToBadge[remaining.tone]}
          icon={remaining.days === null ? 'help-circle-outline' : 'time-outline'}
        />
        <Badge
          label={documents.length > 0 ? (documents.length === 1 ? 'Bid document' : `${documents.length} documents`) : 'No bid documents'}
          tone={documents.length > 0 ? 'info' : 'neutral'}
          icon={documents.length > 0 ? 'document-attach-outline' : 'document-outline'}
        />
        {!compact ? (
          <Badge
            label={verificationLabel(tender.verification_status)}
            tone={verified ? 'success' : 'warning'}
            icon={verified ? 'shield-checkmark-outline' : 'shield-outline'}
          />
        ) : null}
      </View>

      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      <View style={styles.footer}>
        <Ionicons name="globe-outline" size={12} color={colors.textTertiary} />
        <AppText variant="caption" color="textTertiary" numberOfLines={1} style={styles.flex}>
          {tender.source_name || 'Public source'}
        </AppText>
        <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} />
      </View>
    </Pressable>
  );
});

function MetaItem({
  icon,
  text,
  muted,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  text: string;
  muted?: boolean;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.metaItem}>
      <Ionicons name={icon} size={13} color={muted ? colors.textTertiary : colors.textSecondary} />
      <AppText
        variant="caption"
        color={muted ? 'textTertiary' : 'textSecondary'}
        numberOfLines={1}
        style={[styles.metaText, muted && styles.metaMuted]}>
        {text}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radii.lg,
    borderWidth: 1,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  pressed: {
    opacity: 0.96,
    transform: [{ scale: 0.997 }],
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  topBadges: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  categoryPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  categoryText: {
    fontSize: 10.5,
    letterSpacing: 0.2,
  },
  bookmark: {
    padding: 2,
  },
  title: {
    lineHeight: 23,
  },
  orgRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  flex: {
    flex: 1,
  },
  metaGrid: {
    gap: 5,
    marginTop: 2,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  metaText: {
    flex: 1,
  },
  metaMuted: {
    fontStyle: 'italic',
  },
  badgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 2,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 2,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  footerIcon: {
    fontFamily: fonts.medium,
  },
});
