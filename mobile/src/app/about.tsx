import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { IconButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { BrandMark, Screen } from '@/components/ui/screen';
import { API_BASE_URL, API_DOCS_URL, APP_VERSION } from '@/config';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

const REPOSITORY_URL = 'https://github.com/anishacharya95/Bidders-nepal';

export default function AboutScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const open = (url: string) => WebBrowser.openBrowserAsync(url);

  return (
    <Screen>
      <View style={styles.header}>
        <IconButton icon="close" variant="surface" onPress={() => router.back()} accessibilityLabel="Close" />
        <AppText variant="h1">About</AppText>
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Card style={styles.identity}>
          <BrandMark size={56} />
          <View style={styles.identityCopy}>
            <AppText variant="h2">Bidders Nepal</AppText>
            <AppText variant="small" color="textSecondary">
              Independent Nepal public tender aggregator · v{APP_VERSION}
            </AppText>
          </View>
          <Badge label="Not a government agency" tone="neutral" />
        </Card>

        <Card style={styles.card}>
          <AppText variant="h3">What this app does</AppText>
          <AppText variant="small" color="textSecondary">
            Bidders Nepal collects publicly available procurement notices from official Nepal
            government sources, extracts the published details and bid documents, and links every
            record back to its original notice. Nothing is invented: fields the source does not
            publish are shown as unavailable.
          </AppText>
          <View style={styles.bullets}>
            <Bullet text="Automated collection from PPMO, ministries, departments and registered local governments." />
            <Bullet text="Duplicate notices from multiple sources are linked to one canonical record." />
            <Bullet text="Pending records are labelled until an administrator reviews them against the source." />
            <Bullet text="Documents are opened or downloaded from the original government source." />
          </View>
        </Card>

        <Card style={styles.card}>
          <AppText variant="h3">Contact & data corrections</AppText>
          <AppText variant="small" color="textSecondary">
            Found a wrong deadline, missing document or an official source we should cover? Report
            it through the project repository so it can be reviewed and corrected.
          </AppText>
          <Button
            label="Open project repository"
            icon="logo-github"
            variant="secondary"
            onPress={() => open(REPOSITORY_URL)}
          />
          <Pressable onPress={() => open(API_DOCS_URL)} accessibilityRole="button">
            <AppText variant="caption" color="navy">
              Public API documentation
            </AppText>
          </Pressable>
          <AppText variant="caption" color="textTertiary">
            API: {API_BASE_URL}
          </AppText>
        </Card>

        <Card style={styles.card}>
          <AppText variant="h3">Important disclaimer</AppText>
          <AppText variant="small" color="textSecondary">
            Always confirm the notice, deadline, eligibility and bid documents on the original
            government source before bidding. Bidders Nepal does not endorse any tender and is not
            responsible for decisions made from aggregated data.
          </AppText>
        </Card>

        <View style={[styles.footerCard, { borderColor: colors.border }]}>
          <Ionicons name="shield-checkmark-outline" size={16} color={colors.primary} />
          <AppText variant="caption" color="textTertiary" style={styles.footerText}>
            Public read-only app. No admin credentials are stored on this device.
          </AppText>
        </View>
      </ScrollView>
    </Screen>
  );
}

function Bullet({ text }: { text: string }) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.bullet}>
      <Ionicons name="checkmark-circle" size={14} color={colors.primary} />
      <AppText variant="caption" color="textSecondary" style={styles.bulletText}>
        {text}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  content: {
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.xxxl,
    gap: spacing.lg,
  },
  identity: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    flexWrap: 'wrap',
  },
  identityCopy: { flex: 1, gap: 2 },
  card: { gap: spacing.sm },
  bullets: { gap: spacing.sm, marginTop: spacing.xs },
  bullet: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  bulletText: { flex: 1 },
  footerCard: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
    borderTopWidth: 1,
    paddingTop: spacing.md,
  },
  footerText: { flex: 1 },
});
