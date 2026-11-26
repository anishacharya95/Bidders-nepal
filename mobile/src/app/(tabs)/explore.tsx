import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';

import { FilterSheet } from '@/components/filters/filter-sheet';
import { TenderCard } from '@/components/tender/tender-card';
import { AppText } from '@/components/ui/app-text';
import { IconButton } from '@/components/ui/button';
import { Chip } from '@/components/ui/chip';
import { Screen } from '@/components/ui/screen';
import { SearchField } from '@/components/ui/search-field';
import { SkeletonTenderCard } from '@/components/ui/skeleton';
import { EmptyState, ErrorState } from '@/components/ui/states';
import { useTenderFacets } from '@/hooks/use-tender-facets';
import { useTenderFeed } from '@/hooks/use-tender-feed';
import { pluralise } from '@/lib/format';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing, tabBarSpace } from '@/theme';
import {
  countActiveFilters,
  EMPTY_FILTERS,
  type SortKey,
  type Tender,
  type TenderFilters,
} from '@/types/tender';

const SORT_OPTIONS: { key: SortKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: 'newest', label: 'Newest', icon: 'sparkles-outline' },
  { key: 'closing', label: 'Closing soon', icon: 'alarm-outline' },
  { key: 'oldest', label: 'Oldest', icon: 'time-outline' },
  { key: 'organization', label: 'A–Z', icon: 'business-outline' },
];

export default function ExploreScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    province?: string;
    category?: string;
    status?: string;
    municipality?: string;
    hasDocuments?: string;
    q?: string;
  }>();
  const { colors } = useAppTheme();
  const facets = useTenderFacets();

  const [filterState, setFilterState] = useState<TenderFilters>(() => ({
    ...EMPTY_FILTERS,
    province: params.province ?? null,
    category: params.category ?? null,
    status: params.status ?? null,
    municipality: params.municipality ?? null,
    hasDocuments: params.hasDocuments === '1' ? true : null,
  }));
  const [query, setQuery] = useState(params.q ?? '');
  const [debouncedQuery, setDebouncedQuery] = useState((params.q ?? '').trim());
  const [sort, setSort] = useState<SortKey>('newest');
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => {
    if (params.province || params.category || params.status) {
      setFilterState((current) => ({
        ...current,
        province: params.province ?? current.province,
        category: params.category ?? current.category,
        status: params.status ?? current.status,
        municipality: params.municipality ?? current.municipality,
        hasDocuments: params.hasDocuments === '1' ? true : current.hasDocuments,
      }));
    }
  }, [params.province, params.category, params.status, params.municipality, params.hasDocuments]);

  useEffect(() => {
    if (params.q !== undefined) {
      setQuery(params.q);
      setDebouncedQuery(params.q.trim());
    }
  }, [params.q]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 350);
    return () => clearTimeout(timer);
  }, [query]);

  const filters = useMemo<TenderFilters>(
    () => ({ ...filterState, q: debouncedQuery }),
    [filterState, debouncedQuery],
  );

  const feed = useTenderFeed({ filters, sort });
  const activeCount = countActiveFilters(filters, true);

  const openTender = (tender: Tender) => router.push(`/tender/${tender.id}`);

  const clearFilters = () => {
    setFilterState(EMPTY_FILTERS);
    setQuery('');
  };

  const activeChips = useMemo(() => {
    const chips: { key: keyof TenderFilters; label: string }[] = [];
    if (debouncedQuery) chips.push({ key: 'q', label: `“${debouncedQuery}”` });
    if (filterState.category) chips.push({ key: 'category', label: filterState.category });
    if (filterState.province) chips.push({ key: 'province', label: filterState.province });
    if (filterState.district) chips.push({ key: 'district', label: filterState.district });
    if (filterState.municipality)
      chips.push({ key: 'municipality', label: filterState.municipality });
    if (filterState.hasDocuments) chips.push({ key: 'hasDocuments', label: 'With documents' });
    if (filterState.organization)
      chips.push({ key: 'organization', label: filterState.organization });
    if (filterState.procurementType)
      chips.push({ key: 'procurementType', label: filterState.procurementType });
    if (filterState.ministry) chips.push({ key: 'ministry', label: filterState.ministry });
    if (filterState.source) chips.push({ key: 'source', label: filterState.source });
    if (filterState.hasDocuments === false)
      chips.push({ key: 'hasDocuments', label: 'No documents' });
    if (filterState.status) chips.push({ key: 'status', label: filterState.status });
    if (filterState.verificationStatus)
      chips.push({ key: 'verificationStatus', label: filterState.verificationStatus });
    return chips;
  }, [debouncedQuery, filterState]);

  const removeChip = (key: keyof TenderFilters) => {
    if (key === 'q') {
      setQuery('');
      setDebouncedQuery('');
      return;
    }
    setFilterState((current) => ({ ...current, [key]: null }));
  };

  const showInitialSkeleton = (feed.loading || feed.status === 'idle') && feed.items.length === 0;

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <View style={styles.titleCopy}>
            <AppText variant="h1">Explore tenders</AppText>
            <AppText variant="small" color="textSecondary">
              {feed.status === 'error' && feed.items.length === 0
                ? 'Live feed unavailable'
                : feed.total > 0
                  ? `${pluralise(feed.total, 'notice')} available`
                  : 'Public procurement notices'}
            </AppText>
          </View>
          <IconButton
            icon="refresh"
            variant="surface"
            onPress={feed.refresh}
            accessibilityLabel="Refresh tenders"
          />
        </View>

        <SearchField
          value={query}
          onChangeText={setQuery}
          onClear={() => setQuery('')}
          onSubmit={() => setDebouncedQuery(query.trim())}
          rightIcon="funnel-outline"
          onPressRight={() => setSheetOpen(true)}
        />

        <View style={styles.sortRow}>
          <View
            style={[
              styles.segment,
              { backgroundColor: colors.surfaceMuted, borderColor: colors.border },
            ]}>
            {SORT_OPTIONS.map((option) => {
              const active = sort === option.key;
              return (
                <Pressable
                  key={option.key}
                  onPress={() => setSort(option.key)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  style={[
                    styles.segmentItem,
                    active && { backgroundColor: colors.surface },
                  ]}>
                  <Ionicons
                    name={option.icon}
                    size={13}
                    color={active ? colors.navy : colors.textTertiary}
                  />
                  <AppText
                    variant="caption"
                    style={{
                      color: active ? colors.navy : colors.textTertiary,
                      fontSize: 11.5,
                      fontFamily: active ? 'PlusJakartaSans_600SemiBold' : 'PlusJakartaSans_500Medium',
                    }}>
                    {option.label}
                  </AppText>
                </Pressable>
              );
            })}
          </View>
          <Pressable
            onPress={() => setSheetOpen(true)}
            accessibilityRole="button"
            accessibilityLabel="Open filters"
            style={[
              styles.filterButton,
              {
                backgroundColor: activeCount > 0 ? colors.primary : colors.surface,
                borderColor: activeCount > 0 ? colors.primary : colors.border,
              },
            ]}>
            <Ionicons
              name="options-outline"
              size={15}
              color={activeCount > 0 ? colors.onPrimary : colors.text}
            />
            <AppText
              variant="caption"
              style={{
                color: activeCount > 0 ? colors.onPrimary : colors.text,
                fontSize: 11.5,
                fontFamily: 'PlusJakartaSans_600SemiBold',
              }}>
              {activeCount > 0 ? `Filters · ${activeCount}` : 'Filters'}
            </AppText>
          </Pressable>
        </View>

        {activeChips.length > 0 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.activeChips}>
            {activeChips.map((chip) => (
              <Chip
                key={`${chip.key}-${chip.label}`}
                label={chip.label}
                selected
                icon="close"
                onPress={() => removeChip(chip.key)}
              />
            ))}
            <Pressable onPress={clearFilters} style={styles.clearChip}>
              <AppText variant="caption" color="textSecondary">
                Clear all
              </AppText>
            </Pressable>
          </ScrollView>
        ) : null}
      </View>

      <FlatList
        data={feed.items}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TenderCard tender={item} onPress={() => openTender(item)} />
        )}
        contentContainerStyle={styles.listContent}
        ItemSeparatorComponent={() => <View style={{ height: spacing.md }} />}
        showsVerticalScrollIndicator={false}
        onEndReached={feed.loadMore}
        onEndReachedThreshold={0.4}
        refreshControl={
          <RefreshControl
            refreshing={feed.refreshing}
            onRefresh={feed.refresh}
            tintColor={colors.navy}
            colors={[colors.navy]}
          />
        }
        ListEmptyComponent={
          showInitialSkeleton ? (
            <View style={styles.listGap}>
              <SkeletonTenderCard />
              <SkeletonTenderCard />
              <SkeletonTenderCard />
            </View>
          ) : feed.error ? (
            <ErrorState message={feed.error} onRetry={feed.retry} />
          ) : (
            <EmptyState
              icon="search-outline"
              title="No tenders match"
              message={
                activeCount > 0
                  ? 'Try removing a filter or searching a different notice number, office or district.'
                  : 'The API returned no public notices for this view yet.'
              }
              actionLabel={activeCount > 0 ? 'Clear filters' : undefined}
              onAction={activeCount > 0 ? clearFilters : undefined}
            />
          )
        }
        ListFooterComponent={
          <View style={styles.footer}>
            {feed.loadingMore ? (
              <ActivityIndicator color={colors.navy} />
            ) : feed.moreError ? (
              <Pressable onPress={feed.loadMore}>
                <AppText variant="smallStrong" color="navy">
                  Could not load more · Tap to retry
                </AppText>
              </Pressable>
            ) : feed.items.length > 0 ? (
              <>
                <View style={[styles.footerLine, { backgroundColor: colors.border }]} />
                <AppText variant="caption" color="textTertiary" style={styles.footerText}>
                  Showing {feed.items.length.toLocaleString('en-US')} of{' '}
                  {Math.max(feed.total, feed.loadedRecords).toLocaleString('en-US')} notices
                  {feed.loadedRecords > feed.items.length
                    ? ' · scroll for more'
                    : feed.hasMore
                      ? ' · more available'
                      : ' · all loaded'}
                </AppText>
                <AppText variant="caption" color="textTertiary" style={styles.footerText}>
                  Sorting and duplicate removal apply to the loaded feed window.
                </AppText>
              </>
            ) : null}
          </View>
        }
      />

      <FilterSheet
        visible={sheetOpen}
        filters={filterState}
        categories={facets.categories}
        procurementTypes={facets.procurementTypes}
        ministries={facets.ministries}
        provinces={facets.provinces}
        districts={facets.districts}
        municipalities={facets.municipalities}
        organizations={facets.organizations}
        sources={facets.sources}
        onClose={() => setSheetOpen(false)}
        onApply={(next) => setFilterState({ ...next, q: filterState.q })}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    gap: spacing.md,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  titleCopy: {
    gap: 2,
  },
  sortRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  segment: {
    flex: 1,
    flexDirection: 'row',
    borderRadius: radii.md,
    borderWidth: 1,
    padding: 3,
    gap: 2,
  },
  segmentItem: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    height: 34,
    borderRadius: radii.sm,
  },
  filterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    height: 40,
    paddingHorizontal: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
  },
  activeChips: {
    gap: spacing.sm,
    paddingRight: spacing.xl,
    alignItems: 'center',
  },
  clearChip: {
    paddingHorizontal: 6,
    paddingVertical: 4,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: tabBarSpace + spacing.xl,
    paddingTop: spacing.xs,
  },
  listGap: {
    gap: spacing.md,
  },
  footer: {
    alignItems: 'center',
    gap: spacing.sm,
    paddingTop: spacing.xl,
  },
  footerLine: {
    width: 44,
    height: 1,
    marginBottom: spacing.xs,
  },
  footerText: {
    textAlign: 'center',
    maxWidth: 320,
  },
});
