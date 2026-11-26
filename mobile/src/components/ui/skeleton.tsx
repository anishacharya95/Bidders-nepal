import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View, type ViewStyle } from 'react-native';

import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';

export function Skeleton({ width, height = 12, style }: { width?: number | `${number}%`; height?: number; style?: ViewStyle }) {
  const { colors } = useAppTheme();
  const opacity = useRef(new Animated.Value(0.55)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 750, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.55, duration: 750, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      style={[
        { backgroundColor: colors.skeleton, borderRadius: radii.sm, height, opacity },
        width !== undefined ? { width } : styles.flex,
        style,
      ]}
    />
  );
}

export function SkeletonTenderCard() {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <View style={styles.row}>
        <Skeleton width={70} height={20} />
        <Skeleton width={54} height={20} />
      </View>
      <Skeleton height={16} />
      <Skeleton width="82%" height={16} />
      <Skeleton width="55%" height={12} />
      <View style={styles.row}>
        <Skeleton width="38%" height={12} />
        <Skeleton width="30%" height={12} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { alignSelf: 'stretch' },
  card: {
    borderRadius: radii.lg,
    borderWidth: 1,
    padding: spacing.lg,
    gap: spacing.md,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    alignItems: 'center',
  },
});
