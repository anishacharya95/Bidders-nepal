import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { TenderCard } from '@/components/tender/tender-card';
import { AppText } from '@/components/ui/app-text';
import { SkeletonTenderCard } from '@/components/ui/skeleton';
import { EmptyState, ErrorState } from '@/components/ui/states';
import type { TenderFeedResult } from '@/hooks/use-tender-feed';
import { useAppTheme } from '@/providers/theme-provider';
import { spacing } from '@/theme';
import type { Tender } from '@/types/tender';

export function FeedList({
  feed,
  onOpen,
  emptyTitle,
  emptyMessage,
  top,
}: {
  feed: TenderFeedResult;
  onOpen: (tender: Tender) => void;
  emptyTitle: string;
  emptyMessage: string;
  top?: React.ReactNode;
}) {
  const { colors } = useAppTheme();
  const showSkeleton = (feed.loading || feed.status === 'idle') && feed.items.length === 0;

  return (
    <FlatList
      data={feed.items}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <TenderCard tender={item} onPress={() => onOpen(item)} />}
      ListHeaderComponent={top ? <>{top}</> : undefined}
      ListEmptyComponent={
        showSkeleton ? (
          <View style={styles.gap}>
            <SkeletonTenderCard />
            <SkeletonTenderCard />
            <SkeletonTenderCard />
          </View>
        ) : feed.error ? (
          <ErrorState message={feed.error} onRetry={feed.retry} />
        ) : (
          <EmptyState icon="documents-outline" title={emptyTitle} message={emptyMessage} />
        )
      }
      ListFooterComponent={
        feed.items.length > 0 ? (
          <AppText variant="caption" color="textTertiary" style={styles.footer}>
            Showing {feed.items.length.toLocaleString('en-US')} of{' '}
            {Math.max(feed.total, feed.items.length).toLocaleString('en-US')} records
            {feed.hasMore ? ' · scroll for more' : ' · all loaded'}
          </AppText>
        ) : undefined
      }
      contentContainerStyle={styles.content}
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
    />
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xxxl,
  },
  gap: {
    gap: spacing.md,
  },
  footer: {
    textAlign: 'center',
    paddingTop: spacing.xl,
  },
});
