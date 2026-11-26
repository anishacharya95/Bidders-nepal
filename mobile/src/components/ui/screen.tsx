import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { Pressable, StyleSheet, View, type ViewStyle } from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

import { AppText } from '@/components/ui/app-text';
import { useAppTheme } from '@/providers/theme-provider';
import { maxContentWidth, radii, spacing } from '@/theme';

export function Screen({
  children,
  edges = ['top'],
  style,
  background = 'background',
}: {
  children: React.ReactNode;
  edges?: Edge[];
  style?: ViewStyle;
  background?: 'background' | 'backgroundAlt' | 'surface';
}) {
  const { colors } = useAppTheme();
  return (
    <SafeAreaView
      edges={edges}
      style={[styles.screen, { backgroundColor: colors[background] }, style]}>
      <View style={styles.inner}>{children}</View>
    </SafeAreaView>
  );
}

export function SectionHeader({
  title,
  subtitle,
  actionLabel,
  onPressAction,
  icon,
}: {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onPressAction?: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.sectionHeader}>
      <View style={styles.sectionTitleWrap}>
        <View style={styles.sectionTitleRow}>
          {icon ? <Ionicons name={icon} size={17} color={colors.navy} /> : null}
          <AppText variant="h2">{title}</AppText>
        </View>
        {subtitle ? (
          <AppText variant="small" color="textSecondary" style={styles.sectionSubtitle}>
            {subtitle}
          </AppText>
        ) : null}
      </View>
      {actionLabel && onPressAction ? (
        <Pressable
          onPress={onPressAction}
          accessibilityRole="button"
          hitSlop={8}
          style={({ pressed }) => [styles.action, pressed && { opacity: 0.6 }]}>
          <AppText variant="smallStrong" color="navy">
            {actionLabel}
          </AppText>
          <Ionicons name="chevron-forward" size={14} color={colors.navy} />
        </Pressable>
      ) : null}
    </View>
  );
}

export function BrandMark({ size = 42 }: { size?: number }) {
  const { colors } = useAppTheme();
  return (
    <View
      style={[
        styles.brandMark,
        {
          width: size,
          height: size,
          borderRadius: size * 0.3,
          borderColor: colors.border,
        },
      ]}>
      <Image
        source={require('@/assets/images/app-icon.png')}
        style={{ width: size, height: size }}
        contentFit="cover"
        accessibilityLabel="Bidders Nepal logo"
      />
    </View>
  );
}

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.brandRow}>
      <BrandMark size={compact ? 36 : 42} />
      <View>
        <AppText variant="h3" style={styles.brandName}>
          Bidders Nepal
        </AppText>
        <AppText variant="caption" color="textTertiary" style={styles.brandTag}>
          TENDER INTELLIGENCE
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  inner: {
    flex: 1,
    width: '100%',
    maxWidth: maxContentWidth,
    alignSelf: 'center',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  sectionTitleWrap: {
    flex: 1,
    gap: 2,
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  sectionSubtitle: {
    marginTop: 2,
  },
  action: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    paddingVertical: 4,
  },
  brandMark: {
    overflow: 'hidden',
    borderWidth: 1,
    backgroundColor: '#0B1F3A',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  brandName: {
    letterSpacing: -0.3,
  },
  brandTag: {
    letterSpacing: 1.4,
    fontSize: 9,
    marginTop: 1,
  },
});
