import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { IconButton } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/ui/states';
import { useTenderFacets } from '@/hooks/use-tender-facets';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Works: 'construct-outline',
  Goods: 'cube-outline',
  Consultancy: 'people-outline',
  Services: 'briefcase-outline',
  Other: 'apps-outline',
};

export default function CategoriesScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const facets = useTenderFacets();

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <AppText variant="h1">Tender categories</AppText>
          <AppText variant="small" color="textSecondary">
            Counts are calculated from notices currently returned by the API.
          </AppText>
        </View>
        <IconButton icon="close" variant="surface" onPress={() => router.back()} accessibilityLabel="Close" />
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {!facets.loaded ? (
          <View style={styles.grid}>
            {[0, 1, 2, 3].map((key) => (
              <Skeleton key={key} height={108} />
            ))}
          </View>
        ) : facets.categories.length === 0 ? (
          <ErrorState
            message="The API did not return category data yet."
            onRetry={() => router.replace('/categories')}
          />
        ) : (
          <View style={styles.grid}>
            {facets.categories.map((category) => (
              <Pressable
                key={category.value}
                accessibilityRole="button"
                accessibilityLabel={`${category.value}, ${category.count} notices`}
                onPress={() => router.push({ pathname: '/explore', params: { category: category.value } })}
                style={({ pressed }) => [
                  styles.card,
                  { backgroundColor: colors.surface, borderColor: colors.border },
                  pressed && { opacity: 0.85 },
                ]}>
                <View style={[styles.icon, { backgroundColor: colors.navySoft }]}>
                  <Ionicons
                    name={ICONS[category.value] ?? 'albums-outline'}
                    size={18}
                    color={colors.navy}
                  />
                </View>
                <AppText variant="h3">{category.value}</AppText>
                <AppText variant="caption" color="textTertiary">
                  {category.count.toLocaleString('en-US')} notice{category.count === 1 ? '' : 's'}
                </AppText>
              </Pressable>
            ))}
          </View>
        )}
        <AppText variant="caption" color="textTertiary" style={styles.note}>
          Category counts reflect the current public feed window and may change as new notices are
          collected.
        </AppText>
      </ScrollView>
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
  content: {
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.xxxl,
    gap: spacing.lg,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  card: {
    width: '47.5%',
    flexGrow: 1,
    borderRadius: radii.lg,
    borderWidth: 1,
    padding: spacing.lg,
    gap: 5,
  },
  icon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  note: { marginTop: spacing.sm },
});
