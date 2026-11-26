import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { useCallback } from 'react';
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';

import { TenderCard } from '@/components/tender/tender-card';
import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Chip } from '@/components/ui/chip';
import { IconButton } from '@/components/ui/button';
import { SearchField } from '@/components/ui/search-field';
import { SectionHeader, Screen, BrandLockup } from '@/components/ui/screen';
import { Skeleton, SkeletonTenderCard } from '@/components/ui/skeleton';
import { StatCard } from '@/components/ui/stat-card';
import { EmptyState, ErrorState, InlineNotice } from '@/components/ui/states';
import { useTenderFeed } from '@/hooks/use-tender-feed';
import { useTenderStats } from '@/hooks/use-tender-stats';
import { relativeTime } from '@/lib/format';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing, tabBarSpace } from '@/theme';
import { EMPTY_FILTERS, type Tender } from '@/types/tender';

const CATEGORY_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Works: 'construct-outline',
  Goods: 'cube-outline',
  Consultancy: 'people-outline',
  Services: 'briefcase-outline',
  Other: 'apps-outline',
};

export default function HomeScreen() {
  const router = useRouter();
  const { colors, isDark, mode, cycleMode } = useAppTheme();
  const stats = useTenderStats();
  const feed = useTenderFeed({ filters: EMPTY_FILTERS, sort: 'newest' });
  const refreshing = stats.refreshing || feed.refreshing;

  const onRefresh = useCallback(() => {
    stats.refresh();
    feed.refresh();
  }, [feed, stats]);

  const openTender = useCallback(
    (tender: Tender) => router.push(`/tender/${tender.id}`),
    [router],
  );

  const openExplore = useCallback(
    (params?: Record<string, string>) =>
      router.push({ pathname: '/explore', params: params ?? {} }),
    [router],
  );

  const latest = feed.items.slice(0, 5);
  const recentlyPublished = stats.recent.slice(0, 5);
  const hasStatsError = !!stats.error && stats.loadedCount === 0;
  const updated = relativeTime(stats.updatedAt);

  return (
    <Screen>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.navy}
            colors={[colors.navy]}
          />
        }>
        <View style={styles.header}>
          <BrandLockup />
          <IconButton
            icon={isDark ? 'sunny-outline' : mode === 'light' ? 'contrast-outline' : 'moon-outline'}
            variant="surface"
            onPress={cycleMode}
            accessibilityLabel="Change appearance"
          />
        </View>

        <View style={styles.greeting}>
          <AppText variant="caption" color="textTertiary" style={styles.eyebrow}>
            NAMASTE, BIDDER
          </AppText>
          <AppText variant="display">
            Find your next{'\n'}government contract.
          </AppText>
          <AppText variant="body" color="textSecondary" style={styles.greetingBody}>
            Live public procurement notices from Nepal government agencies, municipalities and
            infrastructure departments.
          </AppText>
        </View>

        <SearchField
          editable={false}
          onPress={() => router.push('/search')}
          rightIcon="options-outline"
          onPressRight={() => openExplore()}
        />

        <View style={styles.quickRow}>
          {[
            { label: 'Latest', icon: 'sparkles-outline' as const, path: '/latest' },
            { label: 'Closing soon', icon: 'alarm-outline' as const, path: '/closing-soon' },
            { label: 'Categories', icon: 'grid-outline' as const, path: '/categories' },
          ].map((item) => (
            <Pressable
              key={item.path}
              onPress={() => router.push(item.path)}
              accessibilityRole="button"
              accessibilityLabel={item.label}
              style={({ pressed }) => [
                styles.quickLink,
                { backgroundColor: colors.surface, borderColor: colors.border },
                pressed && { opacity: 0.8 },
              ]}>
              <Ionicons name={item.icon} size={15} color={colors.navy} />
              <AppText variant="caption" style={{ fontFamily: 'PlusJakartaSans_600SemiBold' }}>
                {item.label}
              </AppText>
            </Pressable>
          ))}
        </View>

        {hasStatsError ? (
          <ErrorState message={stats.error ?? ''} onRetry={stats.refresh} />
        ) : (
          <>
            <LinearGradient
              colors={isDark ? [colors.heroFrom, colors.heroTo] : ['#0B1F3A', '#1B3A63']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.hero}>
              <View style={styles.heroOrbLarge} />
              <View style={styles.heroOrbSmall} />
              <View style={styles.heroTop}>
                <View style={styles.livePill}>
                  <View style={styles.liveDot} />
                  <AppText variant="caption" style={styles.liveText}>
                    LIVE PUBLIC FEED
                  </AppText>
                </View>
                <Pressable
                  onPress={onRefresh}
                  accessibilityRole="button"
                  accessibilityLabel="Refresh dashboard"
                  style={({ pressed }) => [styles.heroRefresh, pressed && { opacity: 0.6 }]}>
                  <Ionicons name="refresh" size={15} color="#FFFFFF" />
                </Pressable>
              </View>

              <View style={styles.heroCount}>
                {stats.loading ? (
                  <Skeleton width={110} height={44} style={{ backgroundColor: '#FFFFFF22' }} />
                ) : (
                  <AppText style={styles.heroNumber}>
                    {stats.total.toLocaleString('en-US')}
                  </AppText>
                )}
                <AppText style={styles.heroCaption}>notices tracked</AppText>
              </View>

              <View style={styles.heroFooter}>
                <View style={styles.heroFooterItem}>
                  <Ionicons name="shield-checkmark-outline" size={14} color="#9BE3C0" />
                  <AppText style={styles.heroFooterText}>
                    {stats.verified.toLocaleString('en-US')} verified
                  </AppText>
                </View>
                <View style={styles.heroDivider} />
                <View style={styles.heroFooterItem}>
                  <Ionicons name="pulse-outline" size={14} color="#9BC3FF" />
                  <AppText style={styles.heroFooterText}>
                    API live{updated ? ` · ${updated}` : ''}
                  </AppText>
                </View>
              </View>
            </LinearGradient>

            <View style={styles.statsGrid}>
              <View style={styles.statsRow}>
                <StatCard
                  label="Open tenders"
                  value={stats.open}
                  hint={stats.openEstimated ? 'Estimated from loaded notices' : 'Reported by the API'}
                  icon="lock-open-outline"
                  tone="success"
                  loading={stats.loading}
                />
                <StatCard
                  label="Closing soon"
                  value={stats.closingSoon}
                  hint={`Next 7 days · ${stats.loadedCount} loaded`}
                  icon="alarm-outline"
                  tone="warning"
                  loading={stats.loading}
                />
              </View>
              <View style={styles.statsRow}>
                <StatCard
                  label="Verified"
                  value={stats.verified}
                  hint="Reviewed by Bidders Nepal"
                  icon="shield-checkmark-outline"
                  tone="navy"
                  loading={stats.loading}
                />
                <StatCard
                  label="Pending review"
                  value={stats.pending}
                  hint="Awaiting verification"
                  icon="hourglass-outline"
                  tone="info"
                  loading={stats.loading}
                />
              </View>
            </View>

            {!stats.loading && stats.total > 0 && stats.verified === 0 ? (
              <InlineNotice
                tone="warning"
                icon="shield-outline"
                title="No verified notices yet"
                message={`The API currently returns ${stats.pending.toLocaleString('en-US')} pending record${stats.pending === 1 ? '' : 's'} and 0 verified notices. Pending records are clearly labelled and always link back to the original government source.`}
              />
            ) : null}

            {stats.provinces.length > 0 ? (
              <View>
                <SectionHeader
                  title="Browse by province"
                  subtitle="Only provinces reported in the current feed are listed."
                  actionLabel="All"
                  onPressAction={() => openExplore()}
                />
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.chipRow}>
                  {stats.provinces.map((province) => (
                    <Chip
                      key={province.value}
                      label={province.value}
                      count={province.count}
                      icon="location-outline"
                      onPress={() => openExplore({ province: province.value })}
                    />
                  ))}
                </ScrollView>
              </View>
            ) : null}

            {stats.categories.length > 0 ? (
              <View>
                <SectionHeader
                  title="Popular categories"
                  subtitle={`Distribution across the latest ${stats.loadedCount} notices loaded.`}
                  actionLabel="Explore"
                  onPressAction={() => openExplore()}
                />
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.categoryRow}>
                  {stats.categories.map((category) => (
                    <Pressable
                      key={category.value}
                      onPress={() => openExplore({ category: category.value })}
                      accessibilityRole="button"
                      accessibilityLabel={`Browse ${category.value} tenders`}
                      style={({ pressed }) => [
                        styles.categoryCard,
                        {
                          backgroundColor: colors.surface,
                          borderColor: colors.border,
                        },
                        pressed && { opacity: 0.85 },
                      ]}>
                      <View style={[styles.categoryIcon, { backgroundColor: colors.navySoft }]}>
                        <Ionicons
                          name={CATEGORY_ICONS[category.value] ?? 'albums-outline'}
                          size={16}
                          color={colors.navy}
                        />
                      </View>
                      <AppText variant="h3" numberOfLines={1}>
                        {category.value}
                      </AppText>
                      <AppText variant="caption" color="textTertiary">
                        {category.count} notice{category.count === 1 ? '' : 's'}
                      </AppText>
                    </Pressable>
                  ))}
                </ScrollView>
              </View>
            ) : null}

            <View>
              <SectionHeader
                title="Recently published"
                subtitle="Newest records added to the public feed."
                actionLabel="See all"
                onPressAction={() => openExplore()}
              />
              {stats.loading ? (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.cardRow}>
                  <View style={{ width: 272 }}>
                    <SkeletonTenderCard />
                  </View>
                  <View style={{ width: 272 }}>
                    <SkeletonTenderCard />
                  </View>
                </ScrollView>
              ) : recentlyPublished.length === 0 ? (
                <EmptyState
                  icon="documents-outline"
                  title="No notices published yet"
                  message="When the API publishes new procurement notices they will appear here."
                />
              ) : (
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.cardRow}>
                  {recentlyPublished.map((tender) => (
                    <TenderCard
                      key={tender.id}
                      tender={tender}
                      compact
                      onPress={() => openTender(tender)}
                    />
                  ))}
                </ScrollView>
              )}
            </View>
          </>
        )}

        <View>
          <SectionHeader
            title="Latest procurement notices"
            subtitle="Newest verified and pending records from the API."
            actionLabel="Explore all"
            onPressAction={() => openExplore()}
          />
          {feed.loading ? (
            <View style={styles.listGap}>
              <SkeletonTenderCard />
              <SkeletonTenderCard />
            </View>
          ) : feed.error && feed.items.length === 0 ? (
            <ErrorState message={feed.error} onRetry={feed.retry} />
          ) : latest.length === 0 ? (
            <EmptyState
              icon="search-outline"
              title="No tenders match"
              message="The API returned no public records. Pull to refresh or explore filters."
              actionLabel="Explore tenders"
              onAction={() => openExplore()}
            />
          ) : (
            <View style={styles.listGap}>
              {latest.map((tender) => (
                <TenderCard key={tender.id} tender={tender} onPress={() => openTender(tender)} />
              ))}
            </View>
          )}
        </View>

        <Pressable
          onPress={() => router.push('/sources')}
          accessibilityRole="button"
          accessibilityLabel="Government procurement sources"
          style={({ pressed }) => [pressed && { opacity: 0.92 }]}>
          <LinearGradient
            colors={isDark ? ['#10233C', '#0B1A2D'] : ['#FFFFFF', '#F2F6FC']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={[styles.sourcesCard, { borderColor: colors.border }]}>
            <View style={[styles.sourcesIcon, { backgroundColor: colors.navySoft }]}>
              <Ionicons name="layers-outline" size={20} color={colors.navy} />
            </View>
            <View style={styles.sourcesCopy}>
              <AppText variant="h3">Government procurement sources</AppText>
              <AppText variant="small" color="textSecondary">
                PPMO, ministries, municipalities and utilities currently covered.
              </AppText>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
          </LinearGradient>
        </Pressable>

        <View style={styles.footer}>
          <Badge label="Independent aggregator" tone="neutral" icon="information-circle-outline" />
          <AppText variant="caption" color="textTertiary" style={styles.footerText}>
            Bidders Nepal is not a government agency. Always confirm deadlines, eligibility and
            documents on the original notice before bidding.
          </AppText>
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: tabBarSpace,
    gap: spacing.xl,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  greeting: {
    gap: spacing.sm,
    marginTop: -spacing.sm,
  },
  eyebrow: {
    letterSpacing: 1.4,
    fontSize: 10.5,
  },
  greetingBody: {
    maxWidth: 420,
  },
  hero: {
    borderRadius: radii.xl,
    padding: spacing.xl,
    overflow: 'hidden',
    gap: spacing.md,
  },
  heroOrbLarge: {
    position: 'absolute',
    width: 190,
    height: 190,
    borderRadius: 95,
    backgroundColor: 'rgba(255,255,255,0.06)',
    top: -70,
    right: -50,
  },
  heroOrbSmall: {
    position: 'absolute',
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: 'rgba(96,165,250,0.16)',
    bottom: -30,
    left: -20,
  },
  heroTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  livePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(255,255,255,0.14)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radii.pill,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#4ADE80',
  },
  liveText: {
    color: '#FFFFFF',
    fontSize: 10,
    letterSpacing: 0.9,
  },
  heroRefresh: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.14)',
  },
  heroCount: {
    gap: 0,
  },
  heroNumber: {
    color: '#FFFFFF',
    fontFamily: 'PlusJakartaSans_800ExtraBold',
    fontSize: 46,
    lineHeight: 54,
    letterSpacing: -1.6,
  },
  heroCaption: {
    color: 'rgba(255,255,255,0.72)',
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 13.5,
  },
  heroFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.xs,
  },
  heroFooterItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  heroFooterText: {
    color: 'rgba(255,255,255,0.82)',
    fontFamily: 'PlusJakartaSans_500Medium',
    fontSize: 11.5,
  },
  heroDivider: {
    width: 1,
    height: 12,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  quickRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  quickLink: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    height: 40,
    borderRadius: radii.md,
    borderWidth: 1,
  },
  statsGrid: {
    gap: spacing.md,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  chipRow: {
    gap: spacing.sm,
    paddingRight: spacing.xl,
  },
  categoryRow: {
    gap: spacing.md,
    paddingRight: spacing.xl,
  },
  categoryCard: {
    width: 132,
    borderRadius: radii.lg,
    borderWidth: 1,
    padding: spacing.md,
    gap: 6,
  },
  categoryIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  cardRow: {
    gap: spacing.md,
    paddingRight: spacing.xl,
  },
  listGap: {
    gap: spacing.md,
  },
  sourcesCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radii.lg,
    borderWidth: 1,
    padding: spacing.lg,
  },
  sourcesIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sourcesCopy: {
    flex: 1,
    gap: 2,
  },
  footer: {
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingBottom: spacing.md,
  },
  footerText: {
    maxWidth: 460,
  },
});
