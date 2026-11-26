import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useAppTheme } from '@/providers/theme-provider';
import { maxContentWidth, radii, spacing } from '@/theme';

interface CardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  padded?: boolean;
  variant?: 'default' | 'muted' | 'navy';
}

export function Card({ children, style, padded = true, variant = 'default' }: CardProps) {
  const { colors, isDark, shadow } = useAppTheme();
  const backgroundColor =
    variant === 'navy' ? colors.navy : variant === 'muted' ? colors.surfaceMuted : colors.surface;

  return (
    <View
      style={[
        styles.card,
        { backgroundColor, borderColor: isDark ? colors.border : colors.border },
        variant === 'navy' ? null : shadow('sm'),
        padded && styles.padded,
        style,
      ]}>
      {children}
    </View>
  );
}

/** Centers content on tablets and web while staying edge-to-edge on phones. */
export function ContentContainer({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[styles.content, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radii.lg,
    borderWidth: 1,
    overflow: 'hidden',
  },
  padded: {
    padding: spacing.lg,
  },
  content: {
    width: '100%',
    maxWidth: maxContentWidth,
    alignSelf: 'center',
  },
});
