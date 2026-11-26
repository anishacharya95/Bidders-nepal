import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { FeedList } from '@/components/tender/feed-list';
import { AppText } from '@/components/ui/app-text';
import { IconButton } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { useTenderFeed } from '@/hooks/use-tender-feed';
import { useAppTheme } from '@/providers/theme-provider';
import { spacing } from '@/theme';
import { EMPTY_FILTERS } from '@/types/tender';

export default function LatestScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const feed = useTenderFeed({ filters: EMPTY_FILTERS, sort: 'newest' });

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <AppText variant="h1">Latest tenders</AppText>
          <AppText variant="small" color="textSecondary">
            Newest public notices added to the API feed.
          </AppText>
        </View>
        <View style={styles.actions}>
          <IconButton icon="refresh" variant="surface" onPress={feed.refresh} accessibilityLabel="Refresh latest tenders" />
          <IconButton icon="close" variant="surface" onPress={() => router.back()} accessibilityLabel="Close" />
        </View>
      </View>
      <FeedList
        feed={feed}
        onOpen={(tender) => router.push(`/tender/${tender.id}`)}
        emptyTitle="No new notices yet"
        emptyMessage="The API has not published new records for this feed yet."
      />
      <View style={[styles.footer, { borderTopColor: colors.border }]}>
        <AppText variant="caption" color="textTertiary">
          Newest first, including records awaiting verification.
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
  footer: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
  },
});
