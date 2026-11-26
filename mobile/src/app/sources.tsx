import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Chip } from '@/components/ui/chip';
import { IconButton } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { EmptyState, InlineNotice } from '@/components/ui/states';
import { useTenderFacets } from '@/hooks/use-tender-facets';
import { groupSources } from '@/lib/tenders';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

export default function SourcesScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const facets = useTenderFacets();
  const groups = groupSources(facets.sources);

  return (
    <Screen>
      <View style={styles.topBar}>
        <IconButton icon="arrow-back" variant="surface" onPress={() => router.back()} />
        <AppText variant="h2">Government sources</AppText>
        <View style={styles.topSpacer} />
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Card style={styles.introCard}>
          <View style={styles.introRow}>
            <View style={[styles.introIcon, { backgroundColor: colors.navySoft }]}>
              <Ionicons name="layers-outline" size={20} color={colors.navy} />
            </View>
            <View style={styles.introCopy}>
              <AppText variant="h3">{facets.sources.length} published sources</AppText>
              <AppText variant="caption" color="textSecondary">
                Across the latest {facets.noticeCount} notices returned by the API.
              </AppText>
            </View>
            <Badge label="Live" tone="success" dot />
          </View>
          <AppText variant="small" color="textSecondary">
            Bidders Nepal collects public tender notices from official government pages. Source
            names below are exactly as published by the API.
          </AppText>
        </Card>

        <InlineNotice
          tone="warning"
          icon="information-circle-outline"
          title="Coverage is limited to what the API returns"
          message="This list is not a claim that every ministry or all 753 local governments are integrated. Coverage grows as the collector and verified sources are added."
        />

        {!facets.loaded ? (
          <Card style={styles.loadingCard}>
            <AppText variant="small" color="textSecondary">
              Loading sources…
            </AppText>
          </Card>
        ) : groups.length === 0 ? (
          <EmptyState
            icon="business-outline"
            title="No sources published yet"
            message="Source information will appear here as soon as the API returns notices with a source name."
          />
        ) : (
          groups.map((group) => (
            <View key={group.key} style={styles.group}>
              <View style={styles.groupHeader}>
                <View style={styles.groupTitleRow}>
                  <AppText variant="h3">{group.title}</AppText>
                  <View style={[styles.countPill, { backgroundColor: colors.surfaceMuted }]}>
                    <AppText variant="caption" color="textSecondary">
                      {group.sources.length}
                    </AppText>
                  </View>
                </View>
                <AppText variant="caption" color="textTertiary">
                  {group.description}
                </AppText>
              </View>
              <Card padded={false}>
                {group.sources.map((source, index) => (
                  <Pressable
                    key={source.value}
                    onPress={() =>
                      router.push({ pathname: '/search', params: { q: source.value } })
                    }
                    accessibilityRole="button"
                    accessibilityLabel={`Search notices from ${source.value}`}
                    style={({ pressed }) => [
                      styles.sourceRow,
                      index < group.sources.length - 1 && {
                        borderBottomColor: colors.border,
                        borderBottomWidth: StyleSheet.hairlineWidth,
                      },
                      pressed && { backgroundColor: colors.surfaceMuted },
                    ]}>
                    <View style={[styles.sourceDot, { backgroundColor: colors.navySoft }]}>
                      <Ionicons name="business-outline" size={13} color={colors.navy} />
                    </View>
                    <AppText variant="small" numberOfLines={2} style={styles.sourceName}>
                      {source.value}
                    </AppText>
                    <Chip label={`${source.count}`} tone="outline" />
                    <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} />
                  </Pressable>
                ))}
              </Card>
            </View>
          ))
        )}

        <View style={styles.footerNote}>
          <AppText variant="caption" color="textTertiary">
            Central procurement coverage includes the Public Procurement Monitoring Office (PPMO)
            when notices are published by that source. Always confirm details on the original
            government notice before submitting a bid.
          </AppText>
        </View>
      </ScrollView>
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
  topSpacer: {
    width: 40,
  },
  content: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.huge,
    gap: spacing.lg,
  },
  introCard: {
    gap: spacing.md,
  },
  introRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  introIcon: {
    width: 42,
    height: 42,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  introCopy: {
    flex: 1,
    gap: 2,
  },
  loadingCard: {
    alignItems: 'center',
  },
  group: {
    gap: spacing.sm,
  },
  groupHeader: {
    gap: 2,
  },
  groupTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  countPill: {
    minWidth: 22,
    height: 19,
    borderRadius: radii.pill,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  sourceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  sourceDot: {
    width: 28,
    height: 28,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sourceName: {
    flex: 1,
  },
  footerNote: {
    paddingTop: spacing.sm,
  },
});
