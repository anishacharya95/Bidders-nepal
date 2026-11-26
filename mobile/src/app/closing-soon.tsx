import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { fetchClosingSoonTenders } from '@/api/tenders';
import { errorMessage } from '@/api/client';
import { TenderCard } from '@/components/tender/tender-card';
import { AppText } from '@/components/ui/app-text';
import { IconButton } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { SkeletonTenderCard } from '@/components/ui/skeleton';
import { EmptyState, ErrorState } from '@/components/ui/states';
import { CLOSING_SOON_DAYS } from '@/config';
import { useAppTheme } from '@/providers/theme-provider';
import { spacing } from '@/theme';
import type { Tender } from '@/types/tender';

export default function ClosingSoonScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const [items, setItems] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    if (mode === 'refresh') setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const rows = await fetchClosingSoonTenders(CLOSING_SOON_DAYS, 100);
      setItems(rows);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load('initial');
  }, [load]);

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <AppText variant="h1">Closing soon</AppText>
          <AppText variant="small" color="textSecondary">
            Open notices with deadlines in the next {CLOSING_SOON_DAYS} days, earliest first.
          </AppText>
        </View>
        <View style={styles.actions}>
          <IconButton icon="refresh" variant="surface" onPress={() => load('refresh')} accessibilityLabel="Refresh closing soon" />
          <IconButton icon="close" variant="surface" onPress={() => router.back()} accessibilityLabel="Close" />
        </View>
      </View>

      <FlatList
        data={items}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TenderCard tender={item} onPress={() => router.push(`/tender/${item.id}`)} />
        )}
        contentContainerStyle={styles.content}
        ItemSeparatorComponent={() => <View style={{ height: spacing.md }} />}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => load('refresh')}
            tintColor={colors.navy}
            colors={[colors.navy]}
          />
        }
        ListEmptyComponent={
          loading ? (
            <View style={styles.gap}>
              <SkeletonTenderCard />
              <SkeletonTenderCard />
            </View>
          ) : error ? (
            <ErrorState message={error} onRetry={() => load('initial')} />
          ) : (
            <EmptyState
              icon="alarm-outline"
              title="Nothing closing this week"
              message="No open tenders with a published deadline inside the next seven days."
            />
          )
        }
        ListFooterComponent={
          loading ? <ActivityIndicator color={colors.navy} style={styles.loader} /> : undefined
        }
      />
      <View style={[styles.note, { borderTopColor: colors.border }]}>
        <Ionicons name="information-circle-outline" size={14} color={colors.textTertiary} />
        <AppText variant="caption" color="textTertiary" style={styles.noteText}>
          Deadlines come from the source notice. Always confirm the closing time on the official
          document before submitting a bid.
        </AppText>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  headerCopy: { flex: 1, gap: 2 },
  actions: { flexDirection: 'row', gap: spacing.sm },
  content: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.xs,
    paddingBottom: spacing.xxxl,
  },
  gap: { gap: spacing.md },
  loader: { paddingTop: spacing.lg },
  note: {
    flexDirection: 'row',
    gap: 6,
    alignItems: 'flex-start',
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
  },
  noteText: { flex: 1 },
});
