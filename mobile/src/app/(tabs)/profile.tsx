import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { clearApiCache } from '@/api/client';
import { checkApiHealth } from '@/api/tenders';
import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Chip } from '@/components/ui/chip';
import { BrandMark, SectionHeader, Screen } from '@/components/ui/screen';
import { InlineNotice } from '@/components/ui/states';
import { API_BASE_URL, API_DOCS_URL, APP_VERSION } from '@/config';
import { clearTenderCache } from '@/lib/tender-cache';
import { useAppTheme } from '@/providers/theme-provider';
import { useNotifications } from '@/providers/notification-provider';
import { useSavedTenders } from '@/providers/saved-provider';
import { radii, spacing, tabBarSpace, type ThemeMode } from '@/theme';

const THEME_OPTIONS: { mode: ThemeMode; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { mode: 'system', label: 'System', icon: 'phone-portrait-outline' },
  { mode: 'light', label: 'Light', icon: 'sunny-outline' },
  { mode: 'dark', label: 'Dark', icon: 'moon-outline' },
];

export default function ProfileScreen() {
  const router = useRouter();
  const { colors, mode, setMode } = useAppTheme();
  const { saved } = useSavedTenders();
  const { unreadCount } = useNotifications();

  const [health, setHealth] = useState<{
    state: 'idle' | 'checking' | 'ok' | 'fail';
    latency?: number;
  }>({ state: 'idle' });
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);

  const checkHealth = async () => {
    setHealth({ state: 'checking' });
    const result = await checkApiHealth();
    setHealth({ state: result.ok ? 'ok' : 'fail', latency: result.latencyMs });
  };

  const clearCache = async () => {
    await clearTenderCache();
    clearApiCache();
    setCacheMessage('Local cache cleared. Saved tenders and preferences were kept.');
  };

  const openDocs = async () => {
    await WebBrowser.openBrowserAsync(API_DOCS_URL);
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <AppText variant="h1">Profile</AppText>
          <Badge label="Guest" tone="neutral" icon="person-outline" />
        </View>

        <Card style={styles.identityCard}>
          <View style={styles.identityRow}>
            <BrandMark size={56} />
            <View style={styles.identityCopy}>
              <AppText variant="h2">Bidder</AppText>
              <AppText variant="small" color="textSecondary">
                Local profile · no sign-in required
              </AppText>
            </View>
          </View>
          <View style={styles.metricsRow}>
            <Metric label="Saved" value={saved.length} icon="bookmark-outline" />
            <View style={[styles.metricDivider, { backgroundColor: colors.border }]} />
            <Metric label="Alerts" value={unreadCount} icon="notifications-outline" />
            <View style={[styles.metricDivider, { backgroundColor: colors.border }]} />
            <Metric label="Version" value={APP_VERSION} icon="information-circle-outline" />
          </View>
        </Card>

        <View style={styles.section}>
          <SectionHeader title="Appearance" subtitle="Light, dark, or follow your device." />
          <View style={styles.themeRow}>
            {THEME_OPTIONS.map((option) => (
              <Chip
                key={option.mode}
                label={option.label}
                icon={option.icon}
                selected={mode === option.mode}
                onPress={() => setMode(option.mode)}
              />
            ))}
          </View>
        </View>

        <View style={styles.section}>
          <SectionHeader title="Your workspace" />
          <Card padded={false}>
            <SettingRow
              icon="bookmark-outline"
              label="Saved tenders"
              value={`${saved.length}`}
              onPress={() => router.push('/saved')}
            />
            <SettingRow
              icon="notifications-outline"
              label="Notification preferences"
              value={unreadCount > 0 ? `${unreadCount} unread` : 'Manage'}
              onPress={() => router.push('/notifications')}
            />
            <SettingRow
              icon="layers-outline"
              label="Government sources"
              value="Coverage"
              onPress={() => router.push('/sources')}
            />
            <SettingRow
              icon="sparkles-outline"
              label="Latest tenders"
              value="Newest"
              onPress={() => router.push('/latest')}
            />
            <SettingRow
              icon="alarm-outline"
              label="Closing soon"
              value="Next 7 days"
              onPress={() => router.push('/closing-soon')}
            />
            <SettingRow
              icon="grid-outline"
              label="Tender categories"
              value="Browse"
              onPress={() => router.push('/categories')}
            />
            <SettingRow
              icon="information-circle-outline"
              label="About & contact"
              value="Info"
              onPress={() => router.push('/about')}
              last
            />
          </Card>
        </View>

        <View style={styles.section}>
          <SectionHeader title="Data & API" subtitle="Live public feed from the Bidders Nepal API." />
          <Card style={styles.apiCard}>
            <View style={styles.apiRow}>
              <View style={[styles.apiIcon, { backgroundColor: colors.navySoft }]}>
                <Ionicons name="server-outline" size={17} color={colors.navy} />
              </View>
              <View style={styles.apiCopy}>
                <AppText variant="smallStrong">API endpoint</AppText>
                <AppText variant="caption" color="textSecondary" numberOfLines={1}>
                  {API_BASE_URL}
                </AppText>
              </View>
              <Badge
                label={
                  health.state === 'checking'
                    ? 'Checking'
                    : health.state === 'ok'
                      ? 'Online'
                      : health.state === 'fail'
                        ? 'Offline'
                        : 'Unknown'
                }
                tone={
                  health.state === 'ok'
                    ? 'success'
                    : health.state === 'fail'
                      ? 'danger'
                      : 'neutral'
                }
                dot
              />
            </View>
            {health.state === 'ok' && health.latency ? (
              <AppText variant="caption" color="textTertiary">
                Responded in {health.latency} ms.
              </AppText>
            ) : null}
            {health.state === 'fail' ? (
              <AppText variant="caption" color="textSecondary">
                The API did not respond. Free Render hosting can take up to a minute to wake.
              </AppText>
            ) : null}
            <View style={styles.apiActions}>
              <Button
                label="Check API status"
                icon="pulse-outline"
                variant="secondary"
                size="sm"
                onPress={checkHealth}
                loading={health.state === 'checking'}
                style={styles.apiButton}
              />
              <Button
                label="API docs"
                icon="document-text-outline"
                variant="ghost"
                size="sm"
                onPress={openDocs}
                style={styles.apiButton}
              />
            </View>
            <Pressable onPress={clearCache} accessibilityRole="button">
              <AppText variant="caption" color="navy">
                Clear local cache
              </AppText>
            </Pressable>
            {cacheMessage ? (
              <AppText variant="caption" color="textSecondary">
                {cacheMessage}
              </AppText>
            ) : null}
          </Card>
          <InlineNotice
            icon="shield-outline"
            title="No credentials in this app"
            message="The mobile app only reads public tender endpoints. Admin tokens and private credentials are never stored or requested."
          />
        </View>

        <View style={styles.section}>
          <SectionHeader title="About Bidders Nepal" />
          <Card style={styles.aboutCard}>
            <AppText variant="small" color="textSecondary">
              Bidders Nepal is an independent tender discovery app for Nepal. It aggregates public
              procurement notices published by government agencies and links every record back to
              its original source.
            </AppText>
            <Row icon="checkmark-circle-outline" text="Verified records have been reviewed by the Bidders Nepal team." />
            <Row icon="time-outline" text="Pending records are published by the source but not yet reviewed." />
            <Row icon="open-outline" text="Documents are served from the original government source." />
            <Row icon="alert-circle-outline" text="Bidders Nepal is not a government agency and does not endorse any tender." />
          </Card>
        </View>

        <View style={styles.footer}>
          <AppText variant="caption" color="textTertiary" style={styles.footerText}>
            Bidders Nepal v{APP_VERSION} · Made for Nepali bidders
          </AppText>
        </View>
      </ScrollView>
    </Screen>
  );
}

function Metric({
  label,
  value,
  icon,
}: {
  label: string;
  value: number | string;
  icon: keyof typeof Ionicons.glyphMap;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.metric}>
      <Ionicons name={icon} size={14} color={colors.textTertiary} />
      <AppText variant="h3">{value}</AppText>
      <AppText variant="caption" color="textTertiary">
        {label}
      </AppText>
    </View>
  );
}

function SettingRow({
  icon,
  label,
  value,
  onPress,
  last,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value?: string;
  onPress?: () => void;
  last?: boolean;
}) {
  const { colors } = useAppTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.settingRow,
        !last && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth },
        pressed && { backgroundColor: colors.surfaceMuted },
      ]}>
      <View style={[styles.settingIcon, { backgroundColor: colors.surfaceMuted }]}>
        <Ionicons name={icon} size={15} color={colors.navy} />
      </View>
      <AppText variant="smallStrong" style={styles.settingLabel}>
        {label}
      </AppText>
      {value ? (
        <AppText variant="caption" color="textTertiary">
          {value}
        </AppText>
      ) : null}
      <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} />
    </Pressable>
  );
}

function Row({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={14} color={colors.textTertiary} />
      <AppText variant="caption" color="textSecondary" style={styles.rowText}>
        {text}
      </AppText>
    </View>
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
  },
  identityCard: {
    gap: spacing.lg,
  },
  identityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  identityCopy: {
    flex: 1,
    gap: 2,
  },
  metricsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  metric: {
    flex: 1,
    alignItems: 'center',
    gap: 3,
  },
  metricDivider: {
    width: StyleSheet.hairlineWidth,
    height: 34,
  },
  section: {
    gap: spacing.md,
  },
  themeRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    flexWrap: 'wrap',
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  settingIcon: {
    width: 30,
    height: 30,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  settingLabel: {
    flex: 1,
  },
  apiCard: {
    gap: spacing.md,
  },
  apiRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  apiIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  apiCopy: {
    flex: 1,
    gap: 1,
  },
  apiActions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  apiButton: {
    flex: 1,
  },
  aboutCard: {
    gap: spacing.md,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  rowText: {
    flex: 1,
  },
  footer: {
    alignItems: 'center',
  },
  footerText: {
    textAlign: 'center',
  },
});
