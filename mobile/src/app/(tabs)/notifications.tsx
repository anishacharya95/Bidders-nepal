import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  View,
} from 'react-native';

import { errorMessage } from '@/api/client';
import { fetchAllTenders } from '@/api/tenders';
import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { Button, IconButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Screen } from '@/components/ui/screen';
import { EmptyState, InlineNotice } from '@/components/ui/states';
import { MAX_PAGE_SIZE } from '@/config';
import { relativeTime } from '@/lib/format';
import { useAppTheme } from '@/providers/theme-provider';
import {
  useNotifications,
  type AppNotification,
  type NotificationPrefs,
  type NotificationType,
} from '@/providers/notification-provider';
import { spacing, tabBarSpace } from '@/theme';
import { EMPTY_FILTERS } from '@/types/tender';

const PREF_ROWS: { key: keyof NotificationPrefs; label: string; description: string }[] = [
  {
    key: 'newTenders',
    label: 'Newly published tenders',
    description: 'New records that appear in the public feed.',
  },
  {
    key: 'closingSoon',
    label: 'Closing-soon deadlines',
    description: 'Open tenders with 3 days or less remaining.',
  },
  {
    key: 'deadlineChanges',
    label: 'Deadline changes',
    description: 'When a published submission deadline changes.',
  },
  {
    key: 'newDocuments',
    label: 'New bid documents',
    description: 'When the API starts returning a new document.',
  },
  {
    key: 'amendments',
    label: 'Tender amendments',
    description: 'Status or detail updates from the source.',
  },
];

const TYPE_META: Record<
  NotificationType,
  { label: string; icon: keyof typeof Ionicons.glyphMap; tone: 'info' | 'warning' | 'success' | 'neutral' }
> = {
  new: { label: 'New tender', icon: 'sparkles-outline', tone: 'info' },
  closing: { label: 'Closing soon', icon: 'alarm-outline', tone: 'warning' },
  deadline: { label: 'Deadline changed', icon: 'calendar-outline', tone: 'warning' },
  document: { label: 'New document', icon: 'document-attach-outline', tone: 'info' },
  amendment: { label: 'Tender updated', icon: 'create-outline', tone: 'neutral' },
};

export default function NotificationsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const {
    items,
    unreadCount,
    prefs,
    setPref,
    lastSync,
    syncing,
    syncFromTenders,
    markAllRead,
    markRead,
    clearAll,
    hydrated,
  } = useNotifications();

  const [message, setMessage] = useState<string | null>(null);
  const autoRan = useRef(false);

  const runSync = useCallback(async () => {
    setMessage(null);
    try {
      const page = await fetchAllTenders({
        filters: EMPTY_FILTERS,
        page: 1,
        pageSize: MAX_PAGE_SIZE,
        force: true,
      });
      const result = await syncFromTenders(page.items);
      if (result.baselineCreated) {
        setMessage(
          `Baseline saved from ${result.checked} notices. You will now be alerted when the API data changes.`,
        );
      } else if (result.created === 0) {
        setMessage(`Checked ${result.checked} notices — no changes since the last sync.`);
      } else {
        setMessage(
          `${result.created} update${result.created === 1 ? '' : 's'} detected across ${result.checked} notices.`,
        );
      }
    } catch (caught) {
      setMessage(errorMessage(caught));
    }
  }, [syncFromTenders]);

  useEffect(() => {
    if (!hydrated || autoRan.current) return;
    if (lastSync) return;
    autoRan.current = true;
    void runSync();
  }, [hydrated, lastSync, runSync]);

  const lastSyncLabel = relativeTime(lastSync);

  return (
    <Screen>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={syncing}
            onRefresh={runSync}
            tintColor={colors.navy}
            colors={[colors.navy]}
          />
        }>
        <View style={styles.header}>
          <View style={styles.headerCopy}>
            <AppText variant="h1">Notifications</AppText>
            <AppText variant="small" color="textSecondary">
              {unreadCount > 0
                ? `${unreadCount} unread update${unreadCount === 1 ? '' : 's'}`
                : lastSyncLabel
                  ? `Last checked ${lastSyncLabel}`
                  : 'Change alerts from the live API'}
            </AppText>
          </View>
          <IconButton
            icon="refresh"
            variant="surface"
            onPress={runSync}
            accessibilityLabel="Check for updates"
          />
        </View>

        <Card style={styles.syncCard}>
          <View style={styles.syncRow}>
            <View
              style={[
                styles.syncIcon,
                { backgroundColor: lastSync ? colors.successSoft : colors.warningSoft },
              ]}>
              <Ionicons
                name={lastSync ? 'checkmark-circle-outline' : 'hourglass-outline'}
                size={20}
                color={lastSync ? colors.success : colors.warning}
              />
            </View>
            <View style={styles.syncCopy}>
              <AppText variant="smallStrong">
                {lastSync ? 'Monitoring API changes' : 'Set up change monitoring'}
              </AppText>
              <AppText variant="caption" color="textSecondary">
                {lastSync
                  ? 'Alerts are created only from real differences between snapshots.'
                  : 'Run a first check to save a baseline of the current feed.'}
              </AppText>
            </View>
          </View>
          <Button
            label={syncing ? 'Checking…' : lastSync ? 'Check for updates' : 'Start monitoring'}
            icon={syncing ? undefined : 'sync-outline'}
            onPress={runSync}
            loading={syncing}
            variant="secondary"
            size="sm"
          />
          {message ? (
            <InlineNotice
              icon="information-circle-outline"
              title="Sync result"
              message={message}
            />
          ) : null}
        </Card>

        <View style={styles.section}>
          <AppText variant="h2">Preferences</AppText>
          <Card padded={false}>
            {PREF_ROWS.map((row, index) => (
              <View
                key={row.key}
                style={[
                  styles.prefRow,
                  index < PREF_ROWS.length - 1 && {
                    borderBottomColor: colors.border,
                    borderBottomWidth: StyleSheet.hairlineWidth,
                  },
                ]}>
                <View style={styles.prefCopy}>
                  <AppText variant="smallStrong">{row.label}</AppText>
                  <AppText variant="caption" color="textSecondary">
                    {row.description}
                  </AppText>
                </View>
                <Switch
                  value={prefs[row.key]}
                  onValueChange={(value) => setPref(row.key, value)}
                  trackColor={{ false: colors.border, true: colors.success }}
                  thumbColor="#FFFFFF"
                  ios_backgroundColor={colors.border}
                  accessibilityLabel={`Toggle ${row.label}`}
                />
              </View>
            ))}
          </Card>
          <AppText variant="caption" color="textTertiary">
            These settings apply on this device. Bidders Nepal does not send promotional or
            fabricated alerts.
          </AppText>
        </View>

        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <AppText variant="h2">Updates</AppText>
            {items.length > 0 ? (
              <View style={styles.sectionActions}>
                <Pressable onPress={markAllRead} hitSlop={8}>
                  <AppText variant="caption" color="navy">
                    Mark all read
                  </AppText>
                </Pressable>
                <Pressable onPress={clearAll} hitSlop={8}>
                  <AppText variant="caption" color="textSecondary">
                    Clear
                  </AppText>
                </Pressable>
              </View>
            ) : null}
          </View>

          {items.length === 0 ? (
            <Card>
              <EmptyState
                icon="notifications-off-outline"
                title="No updates detected yet"
                message={
                  lastSync
                    ? 'No deadline, document or tender changes have been observed since the last snapshot.'
                    : 'Start monitoring to save a snapshot of the current feed. Future changes will appear here.'
                }
                actionLabel={lastSync ? undefined : 'Start monitoring'}
                onAction={lastSync ? undefined : runSync}
              />
            </Card>
          ) : (
            <View style={styles.notificationList}>
              {items.map((item) => (
                <NotificationRow
                  key={item.id}
                  item={item}
                  onPress={() => {
                    markRead(item.id);
                    router.push(`/tender/${item.tenderId}`);
                  }}
                />
              ))}
            </View>
          )}
        </View>

        <InlineNotice
          icon="shield-checkmark-outline"
          title="How alerts work"
          message="Each check compares the live API feed with the previous snapshot stored on this device. Notices are only generated for observed changes — new records, deadline changes, new documents, status updates and closing deadlines."
        />
      </ScrollView>
    </Screen>
  );
}

function NotificationRow({ item, onPress }: { item: AppNotification; onPress: () => void }) {
  const { colors } = useAppTheme();
  const meta = TYPE_META[item.type];

  const toneColor =
    meta.tone === 'warning'
      ? colors.warning
      : meta.tone === 'success'
        ? colors.success
        : meta.tone === 'info'
          ? colors.info
          : colors.textSecondary;
  const toneBg =
    meta.tone === 'warning'
      ? colors.warningSoft
      : meta.tone === 'success'
        ? colors.successSoft
        : meta.tone === 'info'
          ? colors.infoSoft
          : colors.surfaceMuted;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${meta.label}: ${item.tenderTitle}`}
      style={({ pressed }) => [
        styles.notificationRow,
        {
          backgroundColor: item.read ? colors.surface : colors.surface,
          borderColor: colors.border,
          opacity: pressed ? 0.85 : 1,
        },
      ]}>
      <View style={[styles.notificationIcon, { backgroundColor: toneBg }]}>
        <Ionicons name={meta.icon} size={18} color={toneColor} />
      </View>
      <View style={styles.notificationCopy}>
        <View style={styles.notificationTop}>
          <Badge label={meta.label} tone={meta.tone === 'neutral' ? 'neutral' : meta.tone} />
          <AppText variant="caption" color="textTertiary">
            {relativeTime(item.createdAt)}
          </AppText>
        </View>
        <AppText variant="smallStrong" numberOfLines={2}>
          {item.tenderTitle}
        </AppText>
        <AppText variant="caption" color="textSecondary">
          {item.message}
        </AppText>
      </View>
      {!item.read ? <View style={[styles.unreadDot, { backgroundColor: colors.info }]} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: tabBarSpace,
    gap: spacing.xl,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  headerCopy: {
    gap: 2,
  },
  syncCard: {
    gap: spacing.md,
  },
  syncRow: {
    flexDirection: 'row',
    gap: spacing.md,
    alignItems: 'center',
  },
  syncIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  syncCopy: {
    flex: 1,
    gap: 2,
  },
  section: {
    gap: spacing.md,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  sectionActions: {
    flexDirection: 'row',
    gap: spacing.lg,
    alignItems: 'center',
  },
  prefRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  prefCopy: {
    flex: 1,
    gap: 2,
  },
  notificationList: {
    gap: spacing.sm,
  },
  notificationRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    borderWidth: 1,
    borderRadius: 16,
    padding: spacing.md,
  },
  notificationIcon: {
    width: 36,
    height: 36,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  notificationCopy: {
    flex: 1,
    gap: 4,
  },
  notificationTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  unreadDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginTop: 6,
  },
});
