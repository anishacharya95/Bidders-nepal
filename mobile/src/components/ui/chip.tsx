import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

interface ChipProps {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  count?: number;
  icon?: keyof typeof Ionicons.glyphMap;
  tone?: 'default' | 'outline';
}

export function Chip({ label, selected, onPress, count, icon, tone = 'default' }: ChipProps) {
  const { colors } = useAppTheme();
  const background = selected
    ? colors.primary
    : tone === 'outline'
      ? 'transparent'
      : colors.surface;
  const borderColor = selected ? colors.primary : colors.border;
  const contentColor = selected ? colors.onPrimary : colors.textSecondary;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      style={({ pressed }) => [
        styles.chip,
        { backgroundColor: background, borderColor },
        pressed && styles.pressed,
      ]}>
      {icon ? <Ionicons name={icon} size={13} color={contentColor} /> : null}
      <AppText variant="smallStrong" style={{ color: contentColor }} numberOfLines={1}>
        {label}
      </AppText>
      {typeof count === 'number' ? (
        <View
          style={[
            styles.count,
            { backgroundColor: selected ? 'rgba(255,255,255,0.18)' : colors.surfaceMuted },
          ]}>
          <AppText
            variant="caption"
            style={{ color: selected ? colors.onPrimary : colors.textTertiary, fontSize: 10.5 }}>
            {count}
          </AppText>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    height: 34,
    borderRadius: radii.pill,
    borderWidth: 1,
    maxWidth: 260,
  },
  pressed: {
    opacity: 0.75,
  },
  count: {
    minWidth: 20,
    paddingHorizontal: 5,
    height: 18,
    borderRadius: radii.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
