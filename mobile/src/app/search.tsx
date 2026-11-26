import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import {
  Keyboard,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';

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
import { useSearchHistory } from '@/providers/search-history-provider';
import { radii, spacing, tabBarSpace } from '@/theme';
import { EMPTY_FILTERS } from '@/types/tender';

const SEARCH_HINTS = [
  'Tender title',
  'Notice number',
  'Government organisation',
  'Municipality',
  'District',
  'Province',
  'Procurement category',
];

export default function SearchScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ q?: string }>();
  const { colors } = useAppTheme();
  const { terms, addTerm, removeTerm, clearTerms } = useSearchHistory();
  const facets = useTenderFacets();

  const [query, setQuery] = useState(params.q ?? '');
  const [submitted, setSubmitted] = useState((params.q ?? '').trim());

  useEffect(() => {
    const timer = setTimeout(() => setSubmitted(query.trim()), 350);
    return () => clearTimeout(timer);
  }, [query]);

  const filters = useMemo(() => ({ ...EMPTY_FILTERS, q: submitted }), [submitted]);
  const feed = useTenderFeed({
    filters,
    sort: 'newest',
    enabled: submitted.length > 0,
  });

  const runSearch = (value: string) => {
    setQuery(value);
    setSubmitted(value.trim());
    addTerm(value);
    Keyboard.dismiss();
  };

  const openTender = (id: number) => {
    if (submitted) addTerm(submitted);
    router.push(`/tender/${id}`);
  };

  const showResults = submitted.length > 0;

  return (
    <Screen>
      <View style={styles.topBar}>
        <IconButton
          icon="arrow-back"
          variant="ghost"
          onPress={() => router.back()}
          accessibilityLabel="Go back"
        />
        <View style={styles.searchWrap}>
          <SearchField
            value={query}
            onChangeText={setQuery}
            onSubmit={() => runSearch(query)}
            onClear={() => setQuery('')}
            autoFocus
            placeholder="Title, notice no., office, district…"
          />
        </View>
        <Pressable onPress={() => router.back()} hitSlop={8} accessibilityRole="button">
          <AppText variant="smallStrong" color="navy">
            Cancel
          </AppText>
        </Pressable>
      </View>

      {!showResults ? (
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          {terms.length > 0 ? (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <AppText variant="label" color="textTertiary">
                  Recent searches
                </AppText>
                <Pressable onPress={clearTerms} hitSlop={8}>
                  <AppText variant="caption" color="navy">
                    Clear
                  </AppText>
                </Pressable>
              </View>
              <View style={styles.wrapRow}>
                {terms.map((term) => (
                  <Pressable
                    key={term}
                    onPress={() => runSearch(term)}
                    onLongPress={() => removeTerm(term)}
                    accessibilityRole="button"
                    style={[
                      styles.recentChip,
                      { backgroundColor: colors.surface, borderColor: colors.border },
                    ]}>
                    <Ionicons name="time-outline" size={13} color={colors.textTertiary} />
                    <AppText variant="small" numberOfLines={1} style={styles.recentText}>
                      {term}
                    </AppText>
                    <Pressable onPress={() => removeTerm(term)} hitSlop={8}>
                      <Ionicons name="close" size={13} color={colors.textTertiary} />
                    </Pressable>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}

          {facets.categories.length > 0 ? (
            <View style={styles.section}>
              <AppText variant="label" color="textTertiary">
                Browse categories
              </AppText>
              <View style={styles.wrapRow}>
                {facets.categories.map((category) => (
                  <Chip
                    key={category.value}
                    label={category.value}
                    count={category.count}
                    onPress={() => runSearch(category.value)}
                  />
                ))}
              </View>
            </View>
          ) : null}

          <View style={styles.section}>
            <AppText variant="label" color="textTertiary">
              What you can search
            </AppText>
            <View style={[styles.hintsCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              {SEARCH_HINTS.map((hint, index) => (
                <View
                  key={hint}
                  style={[
                    styles.hintRow,
                    index < SEARCH_HINTS.length - 1 && {
                      borderBottomColor: colors.border,
                      borderBottomWidth: StyleSheet.hairlineWidth,
                    },
                  ]}>
                  <Ionicons name="search-outline" size={13} color={colors.textTertiary} />
                  <AppText variant="small" color="textSecondary">
                    {hint}
                  </AppText>
                </View>
              ))}
            </View>
            <AppText variant="caption" color="textTertiary">
              Search runs against the live Bidders Nepal API. Results include pending and verified
              public notices.
            </AppText>
          </View>
        </ScrollView>
      ) : (
        <View style={styles.resultsWrap}>
          <View style={styles.resultsHeader}>
            <AppText variant="smallStrong">
              {feed.total > 0 ? pluralise(feed.total, 'result') : 'Search results'}
            </AppText>
            <AppText variant="caption" color="textTertiary" numberOfLines={1}>
              for “{submitted}”
            </AppText>
          </View>

          <ScrollView
            contentContainerStyle={styles.resultsContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}>
            {feed.loading ? (
              <View style={styles.listGap}>
                <SkeletonTenderCard />
                <SkeletonTenderCard />
              </View>
            ) : feed.error ? (
              <ErrorState message={feed.error} onRetry={feed.retry} />
            ) : feed.items.length === 0 ? (
              <EmptyState
                icon="search-outline"
                title="No matching tenders"
                message="Try a shorter phrase, a notice number, or the name of the procuring office."
                actionLabel="Clear search"
                onAction={() => setQuery('')}
              />
            ) : (
              <View style={styles.listGap}>
                {feed.items.map((tender) => (
                  <TenderCard key={tender.id} tender={tender} onPress={() => openTender(tender.id)} />
                ))}
                {feed.hasMore ? (
                  <Pressable
                    onPress={feed.loadMore}
                    style={[styles.loadMore, { borderColor: colors.border }]}>
                    <AppText variant="smallStrong" color="navy">
                      {feed.loadingMore ? 'Loading…' : 'Load more results'}
                    </AppText>
                  </Pressable>
                ) : (
                  <AppText variant="caption" color="textTertiary" style={styles.endNote}>
                    End of results for this search.
                  </AppText>
                )}
              </View>
            )}
          </ScrollView>
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  searchWrap: {
    flex: 1,
  },
  content: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: tabBarSpace,
    gap: spacing.xl,
  },
  section: {
    gap: spacing.md,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  wrapRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  recentChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radii.pill,
    borderWidth: 1,
    maxWidth: '100%',
  },
  recentText: {
    maxWidth: 220,
  },
  hintsCard: {
    borderRadius: radii.lg,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
  },
  hintRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
  },
  resultsWrap: {
    flex: 1,
  },
  resultsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.md,
  },
  resultsContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: tabBarSpace,
  },
  listGap: {
    gap: spacing.md,
  },
  loadMore: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderWidth: 1,
    borderRadius: radii.md,
  },
  endNote: {
    textAlign: 'center',
  },
});
