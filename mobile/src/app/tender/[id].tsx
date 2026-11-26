import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { DocumentRow } from '@/components/tender/document-row';
import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { Button, IconButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Screen } from '@/components/ui/screen';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState, ErrorState, InlineNotice } from '@/components/ui/states';
import { errorMessage } from '@/api/client';
import { fetchAnyTender } from '@/api/tenders';
import { openDocument, shareTenderLink } from '@/lib/documents';
import { formatBudget, formatDate, formatDateTime, remainingLabel } from '@/lib/format';
import {
  documentsFor,
  isOpenTender,
  isVerified,
  organisationDisplayName,
  statusLabel,
  verificationLabel,
} from '@/lib/tenders';
import { getCachedTender, putCachedTender } from '@/lib/tender-cache';
import { useAppTheme } from '@/providers/theme-provider';
import { useSavedTenders } from '@/providers/saved-provider';
import { radii, spacing } from '@/theme';
import type { Tender } from '@/types/tender';

const toneColors = {
  success: '#3DD68C',
  warning: '#F2B356',
  danger: '#F87171',
  neutral: 'rgba(255,255,255,0.7)',
} as const;

export default function TenderDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const tenderId = Number(id);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { colors, isDark } = useAppTheme();
  const { isSaved, toggleSaved } = useSavedTenders();

  const [tender, setTender] = useState<Tender | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [sourceMessage, setSourceMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(tenderId)) {
      setError('This tender link is invalid.');
      setLoading(false);
      return;
    }
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    getCachedTender(tenderId).then((cached) => {
      if (active && cached) setTender(cached);
    });

    fetchAnyTender(tenderId, controller.signal)
      .then((fresh) => {
        if (!active) return;
        setTender(fresh);
        void putCachedTender(fresh);
        setLoading(false);
      })
      .catch((caught) => {
        if (!active || controller.signal.aborted) return;
        setError(errorMessage(caught));
        setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [tenderId, reloadKey]);

  const onShare = useCallback(async () => {
    if (!tender) return;
    const url = tender.source_url;
    if (!url) {
      setSourceMessage('This notice has no public source link to share.');
      return;
    }
    await shareTenderLink(url, tender.title);
  }, [tender]);

  const onSave = useCallback(() => {
    if (!tender) return;
    const nowSaved = toggleSaved(tender);
    if (Platform.OS !== 'web') {
      void Haptics.notificationAsync(
        nowSaved
          ? Haptics.NotificationFeedbackType.Success
          : Haptics.NotificationFeedbackType.Warning,
      );
    }
  }, [tender, toggleSaved]);

  const onOpenSource = useCallback(async () => {
    if (!tender?.source_url) return;
    const result = await openDocument(tender.source_url);
    if (!result.ok) setSourceMessage(result.message ?? 'Could not open the source website.');
  }, [tender]);

  const documents = tender ? documentsFor(tender) : [];
  const remaining = tender ? remainingLabel(tender.deadline) : null;
  const saved = tender ? isSaved(tender.id) : false;

  if (!tender && loading) {
    return <DetailSkeleton onBack={() => router.back()} />;
  }

  if (!tender) {
    return (
      <Screen>
        <View style={styles.topBar}>
          <IconButton icon="arrow-back" variant="surface" onPress={() => router.back()} />
        </View>
        <View style={styles.errorWrap}>
          <ErrorState
            title="Tender unavailable"
            message={error ?? 'This tender could not be loaded.'}
            onRetry={() => setReloadKey((key) => key + 1)}
          />
          <Button
            label="Back to tenders"
            variant="ghost"
            onPress={() => router.back()}
            style={{ marginTop: spacing.md }}
          />
        </View>
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={styles.topBar}>
        <IconButton
          icon="arrow-back"
          variant="surface"
          onPress={() => router.back()}
          accessibilityLabel="Go back"
        />
        <View style={styles.topActions}>
          {loading ? <ActivityIndicator size="small" color={colors.navy} /> : null}
          <IconButton
            icon="share-social-outline"
            variant="surface"
            onPress={onShare}
            accessibilityLabel="Share tender"
          />
          <IconButton
            icon={saved ? 'bookmark' : 'bookmark-outline'}
            variant={saved ? 'navy' : 'surface'}
            onPress={onSave}
            accessibilityLabel={saved ? 'Remove from saved' : 'Save tender'}
          />
        </View>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: 120 + insets.bottom }}>
        <View style={styles.heroWrap}>
          <LinearGradient
            colors={isDark ? ['#0E2138', '#0A1728'] : ['#0B1F3A', '#173A63']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.hero}>
            <View style={[styles.heroOrb, isDark && styles.heroOrbDark]} />
            <View style={styles.badgeRow}>
              <Badge label={tender.category || 'Other'} tone="navy" icon="pricetag-outline" />
              <Badge
                label={statusLabel(tender.status)}
                tone={isOpenTender(tender) ? 'success' : 'neutral'}
                dot
              />
              <Badge
                label={verificationLabel(tender.verification_status)}
                tone={isVerified(tender) ? 'success' : 'warning'}
                icon={isVerified(tender) ? 'shield-checkmark-outline' : 'shield-outline'}
              />
            </View>
            <AppText style={styles.heroTitle}>{tender.title}</AppText>
            <View style={styles.heroOrg}>
              <Ionicons name="business" size={14} color="rgba(255,255,255,0.7)" />
              <AppText style={styles.heroOrgText}>{organisationDisplayName(tender)}</AppText>
            </View>

            <View style={styles.heroFooter}>
              <View>
                <AppText style={styles.heroFooterLabel}>SUBMISSION DEADLINE</AppText>
                <AppText style={styles.heroFooterValue}>
                  {formatDate(tender.deadline) ?? 'Not published'}
                </AppText>
              </View>
              <View style={[styles.remainingPill, { borderColor: 'rgba(255,255,255,0.18)' }]}>
                <View
                  style={[
                    styles.remainingDot,
                    { backgroundColor: remaining ? toneColors[remaining.tone] : '#FFFFFF' },
                  ]}
                />
                <AppText style={styles.remainingText}>{remaining?.label ?? 'No deadline'}</AppText>
              </View>
            </View>
          </LinearGradient>
        </View>

        <View style={styles.body}>
          {!isVerified(tender) ? (
            <InlineNotice
              tone="warning"
              icon="shield-outline"
              title="Pending verification"
              message="This notice has not been verified yet. Confirm the procuring entity, deadline and eligibility on the original source before bidding."
            />
          ) : null}

          {error ? (
            <InlineNotice
              tone="info"
              icon="cloud-offline-outline"
              title="Showing a saved copy"
              message="The live API could not be reached, so this is the version saved on your device."
            />
          ) : null}

          <Card style={styles.card} padded={false}>
            <View style={styles.cardHeader}>
              <AppText variant="h3">Key details</AppText>
              <Ionicons name="document-text-outline" size={17} color={colors.textTertiary} />
            </View>
            <View style={styles.details}>
              <DetailRow icon="barcode-outline" label="Notice number" value={tender.notice_number} />
              <DetailRow icon="pricetags-outline" label="Category" value={tender.category} />
              <DetailRow icon="map-outline" label="Province" value={tender.province} />
              <DetailRow icon="location-outline" label="District" value={tender.district} />
              <DetailRow
                icon="calendar-outline"
                label="Published"
                value={formatDate(tender.published_date)}
              />
              <DetailRow
                icon="alarm-outline"
                label="Submission deadline"
                value={formatDateTime(tender.deadline)}
              />
              <DetailRow
                icon="time-outline"
                label="Remaining time"
                value={remaining?.label ?? null}
              />
              <DetailRow
                icon="cash-outline"
                label="Estimated budget"
                value={formatBudget(tender.estimated_budget_npr)}
              />
              <DetailRow
                icon="shield-outline"
                label="Verification"
                value={verificationLabel(tender.verification_status)}
              />
              <DetailRow
                icon="cloud-outline"
                label="Source"
                value={tender.source_name}
                last
              />
            </View>
          </Card>

          <Card style={styles.card}>
            <AppText variant="h3">Description</AppText>
            <AppText
              variant="body"
              color={tender.description ? 'textSecondary' : 'textTertiary'}
              style={styles.description}>
              {tender.description?.trim() ||
                'No description was published by the source. Open the original notice for full scope, eligibility and submission instructions.'}
            </AppText>
          </Card>

          <View>
            <View style={styles.sectionHeaderRow}>
              <View style={styles.sectionTitle}>
                <AppText variant="h2">Bid documents</AppText>
                <AppText variant="caption" color="textTertiary">
                  {documents.length > 0
                    ? `${documents.length} public document${documents.length === 1 ? '' : 's'} from the original source`
                    : 'No public document URL returned by the API'}
                </AppText>
              </View>
              <Badge
                label={documents.length > 0 ? 'Available' : 'None listed'}
                tone={documents.length > 0 ? 'info' : 'neutral'}
              />
            </View>

            {documents.length === 0 ? (
              <Card style={styles.card}>
                <EmptyState
                  icon="document-outline"
                  title="No bid documents published"
                  message="The API has no public document URL for this notice. Check the original source for attachments."
                  actionLabel={tender.source_url ? 'Open original source' : undefined}
                  onAction={tender.source_url ? onOpenSource : undefined}
                />
              </Card>
            ) : (
              <View style={styles.documentList}>
                {documents.map((doc) => (
                  <DocumentRow key={`${doc.id}-${doc.url}`} document={doc} tenderTitle={tender.title} />
                ))}
              </View>
            )}
          </View>

          <Card style={styles.card}>
            <View style={styles.sourceRow}>
              <View style={[styles.sourceIcon, { backgroundColor: colors.navySoft }]}>
                <Ionicons name="globe-outline" size={19} color={colors.navy} />
              </View>
              <View style={styles.sourceCopy}>
                <AppText variant="smallStrong">Original source website</AppText>
                <AppText
                  variant="caption"
                  color={tender.source_url ? 'textSecondary' : 'textTertiary'}
                  numberOfLines={1}>
                  {tender.source_url ?? 'No public source URL was provided for this notice.'}
                </AppText>
              </View>
            </View>
            <Button
              label="View original notice"
              icon="open-outline"
              onPress={onOpenSource}
              disabled={!tender.source_url}
              size="md"
            />
            {sourceMessage ? (
              <AppText variant="caption" color="textSecondary">
                {sourceMessage}
              </AppText>
            ) : null}
          </Card>

          <View style={styles.metaFooter}>
            <AppText variant="caption" color="textTertiary">
              Record ID {tender.id} · added {formatDate(tender.created_at) ?? 'unknown'}
              {tender.updated_at !== tender.created_at
                ? ` · updated ${formatDate(tender.updated_at) ?? 'unknown'}`
                : ''}
            </AppText>
            <AppText variant="caption" color="textTertiary">
              Bidders Nepal aggregates public notices. Always verify details with the procuring
              entity.
            </AppText>
          </View>
        </View>
      </ScrollView>

      <View
        style={[
          styles.stickyBar,
          {
            backgroundColor: colors.surface,
            borderTopColor: colors.border,
            paddingBottom: Math.max(insets.bottom, spacing.md),
          },
        ]}>
        <Button
          label={saved ? 'Saved' : 'Save'}
          icon={saved ? 'bookmark' : 'bookmark-outline'}
          variant="secondary"
          onPress={onSave}
          style={styles.saveButton}
        />
        <Button
          label="View original notice"
          icon="open-outline"
          size="lg"
          onPress={onOpenSource}
          disabled={!tender.source_url}
          style={styles.primaryButton}
        />
      </View>
    </Screen>
  );
}

function DetailRow({
  icon,
  label,
  value,
  last,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string | null | undefined;
  last?: boolean;
}) {
  const { colors } = useAppTheme();
  const missing = !value || value.trim().length === 0;
  return (
    <View style={[styles.detailRow, !last && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth }]}>
      <View style={styles.detailLabel}>
        <Ionicons name={icon} size={14} color={colors.textTertiary} />
        <AppText variant="small" color="textSecondary">
          {label}
        </AppText>
      </View>
      <AppText
        variant="smallStrong"
        color={missing ? 'textTertiary' : 'text'}
        style={[styles.detailValue, missing && styles.missingValue]}
        numberOfLines={3}>
        {missing ? 'Not provided' : value}
      </AppText>
    </View>
  );
}

function DetailSkeleton({ onBack }: { onBack: () => void }) {
  const { colors } = useAppTheme();
  return (
    <Screen>
      <View style={styles.topBar}>
        <IconButton icon="arrow-back" variant="surface" onPress={onBack} />
      </View>
      <View style={styles.body}>
        <Skeleton height={180} style={{ borderRadius: radii.xl }} />
        <Skeleton height={14} width="70%" />
        <Skeleton height={14} width="45%" />
        <View style={{ height: spacing.md }} />
        <Card style={styles.card}>
          <Skeleton height={12} width="40%" />
          <Skeleton height={12} />
          <Skeleton height={12} width="80%" />
          <Skeleton height={12} width="60%" />
        </Card>
        <AppText variant="caption" color="textTertiary">
          Loading tender from the Bidders Nepal API…
        </AppText>
        <View style={[styles.loadingLine, { backgroundColor: colors.border }]} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
  },
  topActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  heroWrap: {
    paddingHorizontal: spacing.xl,
  },
  hero: {
    borderRadius: radii.xl,
    padding: spacing.xl,
    overflow: 'hidden',
    gap: spacing.md,
  },
  heroOrb: {
    position: 'absolute',
    width: 210,
    height: 210,
    borderRadius: 105,
    backgroundColor: 'rgba(255,255,255,0.05)',
    right: -80,
    top: -70,
  },
  heroOrbDark: {
    backgroundColor: 'rgba(90,150,240,0.10)',
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  heroTitle: {
    color: '#FFFFFF',
    fontFamily: 'PlusJakartaSans_700Bold',
    fontSize: 22,
    lineHeight: 29,
    letterSpacing: -0.4,
  },
  heroOrg: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  heroOrgText: {
    color: 'rgba(255,255,255,0.78)',
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 12.5,
    flex: 1,
  },
  heroFooter: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  heroFooterLabel: {
    color: 'rgba(255,255,255,0.55)',
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 9,
    letterSpacing: 1,
  },
  heroFooterValue: {
    color: '#FFFFFF',
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 14,
    marginTop: 2,
  },
  remainingPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: 'rgba(255,255,255,0.08)',
  },
  remainingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  remainingText: {
    color: '#FFFFFF',
    fontFamily: 'PlusJakartaSans_600SemiBold',
    fontSize: 11,
  },
  body: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    gap: spacing.lg,
  },
  card: {
    gap: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  details: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: 11,
  },
  detailLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    flex: 0.9,
  },
  detailValue: {
    flex: 1.1,
    textAlign: 'right',
  },
  missingValue: {
    fontStyle: 'italic',
  },
  description: {
    lineHeight: 22,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitle: {
    flex: 1,
    gap: 2,
  },
  documentList: {
    gap: spacing.sm,
  },
  sourceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  sourceIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sourceCopy: {
    flex: 1,
    gap: 2,
  },
  metaFooter: {
    gap: 4,
    paddingBottom: spacing.lg,
  },
  stickyBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
  },
  saveButton: {
    width: 108,
  },
  primaryButton: {
    flex: 1,
  },
  errorWrap: {
    padding: spacing.xl,
  },
  loadingLine: {
    height: 1,
    width: '100%',
  },
});
