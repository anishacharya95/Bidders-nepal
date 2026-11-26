import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';

import { TenderCard } from '@/components/tender/tender-card';
import { AppText } from '@/components/ui/app-text';
import { Button, IconButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Screen } from '@/components/ui/screen';
import { EmptyState } from '@/components/ui/states';
import { useAppTheme } from '@/providers/theme-provider';
import { useSavedTenders } from '@/providers/saved-provider';
import { spacing, tabBarSpace } from '@/theme';

export default function SavedScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { saved, clearSaved } = useSavedTenders();
  const [confirmingClear, setConfirmingClear] = useState(false);

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <AppText variant="h1">Saved tenders</AppText>
          <AppText variant="small" color="textSecondary">
            {saved.length === 0
              ? 'Your shortlist of opportunities'
              : `${saved.length} tender${saved.length === 1 ? '' : 's'} saved on this device`}
          </AppText>
        </View>
        {saved.length > 0 ? (
          <IconButton
            icon="trash-outline"
            variant="surface"
            onPress={() => setConfirmingClear((value) => !value)}
            accessibilityLabel="Clear saved tenders"
          />
        ) : null}
      </View>

      {confirmingClear && saved.length > 0 ? (
        <Card style={styles.confirmCard}>
          <AppText variant="smallStrong">Remove all saved tenders?</AppText>
          <AppText variant="caption" color="textSecondary">
            This only clears the shortlist stored on this device.
          </AppText>
          <View style={styles.confirmActions}>
            <Button
              label="Cancel"
              variant="secondary"
              size="sm"
              onPress={() => setConfirmingClear(false)}
              style={styles.confirmButton}
            />
            <Button
              label="Remove all"
              variant="danger"
              size="sm"
              icon="trash-outline"
              onPress={() => {
                clearSaved();
                setConfirmingClear(false);
              }}
              style={styles.confirmButton}
            />
          </View>
        </Card>
      ) : null}

      <FlatList
        data={saved}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.listContent}
        ItemSeparatorComponent={() => <View style={{ height: spacing.md }} />}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => (
          <TenderCard tender={item} onPress={() => router.push(`/tender/${item.id}`)} />
        )}
        ListEmptyComponent={
          <View style={styles.emptyWrap}>
            <EmptyState
              icon="bookmark-outline"
              title="No saved tenders yet"
              message="Tap the bookmark on any tender to keep it here for quick access."
              actionLabel="Explore tenders"
              onAction={() => router.push('/explore')}
            />
            <Card style={styles.infoCard}>
              <View style={styles.infoRow}>
                <Ionicons name="phone-portrait-outline" size={16} color={colors.textTertiary} />
                <AppText variant="caption" color="textSecondary" style={styles.infoText}>
                  Saved tenders are stored locally on this device. Bidders Nepal does not require an
                  account and never uploads your shortlist.
                </AppText>
              </View>
            </Card>
          </View>
        }
        ListFooterComponent={
          saved.length > 0 ? (
            <Pressable onPress={() => router.push('/explore')} style={styles.footerLink}>
              <AppText variant="smallStrong" color="navy">
                Find more opportunities
              </AppText>
              <Ionicons name="arrow-forward" size={14} color={colors.navy} />
            </Pressable>
          ) : undefined
        }
      />
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
    paddingBottom: spacing.lg,
  },
  headerCopy: {
    gap: 2,
  },
  confirmCard: {
    marginHorizontal: spacing.xl,
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  confirmActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  confirmButton: {
    flex: 1,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: tabBarSpace + spacing.xl,
    flexGrow: 1,
  },
  emptyWrap: {
    gap: spacing.lg,
    paddingTop: spacing.xl,
  },
  infoCard: {
    backgroundColor: 'transparent',
  },
  infoRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  infoText: {
    flex: 1,
  },
  footerLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: spacing.xl,
  },
});
