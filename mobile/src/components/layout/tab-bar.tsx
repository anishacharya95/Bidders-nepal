import { Ionicons } from '@expo/vector-icons';
import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText } from '@/components/ui/app-text';
import { useAppTheme } from '@/providers/theme-provider';
import { useNotifications } from '@/providers/notification-provider';
import { radii, spacing } from '@/theme';

/** Structural type for the tab bar props exposed by expo-router's Tabs. */
interface TabBarProps {
  state: {
    index: number;
    routes: { key: string; name: string; params?: object }[];
  };
  navigateToTab: (routeKey: string) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  emitter?: { emit: (...args: any[]) => any };
}

const TABS: Record<
  string,
  { label: string; icon: keyof typeof Ionicons.glyphMap; activeIcon: keyof typeof Ionicons.glyphMap }
> = {
  index: { label: 'Home', icon: 'home-outline', activeIcon: 'home' },
  explore: { label: 'Explore', icon: 'compass-outline', activeIcon: 'compass' },
  saved: { label: 'Saved', icon: 'bookmark-outline', activeIcon: 'bookmark' },
  documents: { label: 'Docs', icon: 'document-text-outline', activeIcon: 'document-text' },
  notifications: { label: 'Alerts', icon: 'notifications-outline', activeIcon: 'notifications' },
  profile: { label: 'Profile', icon: 'person-outline', activeIcon: 'person' },
};

export function TabBar({ state, navigateToTab, emitter }: TabBarProps) {
  const { colors, shadow } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { unreadCount } = useNotifications();

  return (
    <View
      pointerEvents="box-none"
      style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, Platform.OS === 'web' ? 14 : 8) }]}>
      <View
        style={[
          styles.bar,
          {
            backgroundColor: colors.surface,
            borderColor: colors.border,
          },
          shadow('lg'),
        ]}>
        {state.routes.map((route, index) => {
          const meta = TABS[route.name] ?? {
            label: route.name,
            icon: 'ellipse-outline' as const,
            activeIcon: 'ellipse' as const,
          };
          const focused = state.index === index;

          const onPress = () => {
            const event = emitter?.emit({
              type: 'tabPress',
              target: route.key,
              canPreventDefault: true,
            });
            const prevented = Boolean(event?.defaultPrevented);
            if (!focused && !prevented) {
              navigateToTab(route.key);
            }
          };

          const showBadge = route.name === 'notifications' && unreadCount > 0;

          return (
            <Pressable
              key={route.key}
              onPress={onPress}
              accessibilityRole="tab"
              accessibilityState={focused ? { selected: true } : {}}
              accessibilityLabel={meta.label}
              style={({ pressed }) => [styles.item, pressed && { opacity: 0.7 }]}>
              <View
                style={[
                  styles.iconWrap,
                  focused && { backgroundColor: colors.navySoft },
                ]}>
                <Ionicons
                  name={focused ? meta.activeIcon : meta.icon}
                  size={20}
                  color={focused ? colors.navy : colors.textTertiary}
                />
                {showBadge ? (
                  <View style={[styles.badge, { backgroundColor: colors.danger, borderColor: colors.surface }]}>
                    <AppText variant="caption" style={styles.badgeText}>
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </AppText>
                  </View>
                ) : null}
              </View>
              <AppText
                variant="caption"
                style={[
                  styles.label,
                  { color: focused ? colors.navy : colors.textTertiary },
                  focused && styles.labelActive,
                ]}>
                {meta.label}
              </AppText>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    paddingHorizontal: spacing.md,
  },
  bar: {
    flexDirection: 'row',
    width: '100%',
    maxWidth: 520,
    borderWidth: 1,
    borderRadius: radii.xl,
    paddingVertical: 7,
    paddingHorizontal: 6,
  },
  item: {
    flex: 1,
    alignItems: 'center',
    gap: 3,
  },
  iconWrap: {
    width: 46,
    height: 30,
    borderRadius: radii.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: 6,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 1.5,
    paddingHorizontal: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
  },
  label: {
    fontSize: 9.5,
    lineHeight: 13,
  },
  labelActive: {
    fontFamily: 'PlusJakartaSans_600SemiBold',
  },
});
