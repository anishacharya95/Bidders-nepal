import { useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { fetchRecentDocuments } from '@/api/tenders';
import { errorMessage } from '@/api/client';
import { DocumentRow } from '@/components/tender/document-row';
import { AppText } from '@/components/ui/app-text';
import { Screen } from '@/components/ui/screen';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState, ErrorState } from '@/components/ui/states';
import { pluralise } from '@/lib/format';
import { useAppTheme } from '@/providers/theme-provider';
import { spacing, tabBarSpace } from '@/theme';
import type { TenderDocument } from '@/types/tender';

/**
 * Every document the collector has discovered, newest first. Each row opens the
 * in-app reader (PDF/image) or offers a download for Office formats.
 */
export default function DocumentsScreen() {
  const { colors } = useAppTheme();
  const [documents, setDocuments] = useState<TenderDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (mode: 'initial' | 'refresh') => {
    if (mode === 'refresh') setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const items = await fetchRecentDocuments(60);
      setDocuments(items);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load('initial');
  }, []);

  const showSkeleton = loading && documents.length === 0;

  return (
    <Screen>
      <View style={styles.header}>
        <AppText variant="h1">Documents</AppText>
        <AppText variant="small" color="textSecondary">
          {documents.length > 0
            ? `${pluralise(documents.length, 'public document')} discovered by the collector`
            : 'Bid documents published by Nepali procuring entities'}
        </AppText>
      </View>

      <FlatList
        data={documents}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <DocumentRow document={item} tenderTitle={item.tender_title ?? 'Tender'} />
        )}
        contentContainerStyle={styles.list}
        ItemSeparatorComponent={() => <View style={{ height: spacing.sm }} />}
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
          showSkeleton ? (
            <View style={{ gap: spacing.sm }}>
              <Skeleton height={96} />
              <Skeleton height={96} />
              <Skeleton height={96} />
            </View>
          ) : error ? (
            <ErrorState message={error} onRetry={() => load('initial')} />
          ) : (
            <EmptyState
              icon="document-outline"
              title="No documents discovered yet"
              message="Documents appear here as the collector finds public attachments on tender detail pages."
              actionLabel="Retry"
              onAction={() => load('initial')}
            />
          )
        }
        ListFooterComponent={
          documents.length > 0 ? (
            <AppText variant="caption" color="textTertiary" style={styles.footer}>
              Files stream through Bidders Nepal. The original source link is always kept, so you
              can verify a document at the procuring entity.
            </AppText>
          ) : undefined
        }
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    gap: 2,
  },
  list: {
    paddingHorizontal: spacing.xl,
    paddingBottom: tabBarSpace + spacing.xl,
  },
  footer: {
    paddingTop: spacing.lg,
    textAlign: 'center',
  },
});
