import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { useAppTheme } from '@/providers/theme-provider';
import { fonts, radii, spacing } from '@/theme';

interface SearchFieldProps {
  value?: string;
  placeholder?: string;
  onChangeText?: (value: string) => void;
  onSubmit?: () => void;
  onPress?: () => void;
  editable?: boolean;
  autoFocus?: boolean;
  onClear?: () => void;
  rightIcon?: keyof typeof Ionicons.glyphMap;
  onPressRight?: () => void;
}

export function SearchField({
  value = '',
  placeholder = 'Search tenders, notice numbers, offices…',
  onChangeText,
  onSubmit,
  onPress,
  editable = true,
  autoFocus = false,
  onClear,
  rightIcon,
  onPressRight,
}: SearchFieldProps) {
  const { colors, isDark } = useAppTheme();

  const inner = (
    <View style={[styles.field, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <View style={styles.leftIcon}>
        <Ionicons name="search" size={18} color={colors.textTertiary} />
      </View>
      {editable ? (
        <TextInput
          value={value}
          onChangeText={onChangeText}
          onSubmitEditing={onSubmit}
          placeholder={placeholder}
          placeholderTextColor={colors.textTertiary}
          autoFocus={autoFocus}
          returnKeyType="search"
          autoCorrect={false}
          style={[styles.input, { color: colors.text }]}
          selectionColor={colors.navy}
          accessibilityLabel="Search tenders"
        />
      ) : (
        <Text style={[styles.placeholder, { color: colors.textTertiary }]} numberOfLines={1}>
          {placeholder}
        </Text>
      )}
      {editable && value.length > 0 ? (
        <Pressable
          onPress={onClear}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel="Clear search">
          <Ionicons name="close-circle" size={18} color={colors.textTertiary} />
        </Pressable>
      ) : null}
      {rightIcon ? (
        <Pressable
          onPress={onPressRight}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Open filters"
          style={[
            styles.rightIcon,
            { backgroundColor: isDark ? colors.surfaceMuted : colors.navySoft },
          ]}>
          <Ionicons name={rightIcon} size={16} color={colors.navy} />
        </Pressable>
      ) : null}
    </View>
  );

  if (!editable && onPress) {
    return (
      <Pressable onPress={onPress} accessibilityRole="search" style={styles.wrap}>
        {inner}
      </Pressable>
    );
  }
  return <View style={styles.wrap}>{inner}</View>;
}

const styles = StyleSheet.create({
  wrap: { width: '100%' },
  field: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderWidth: 1,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    height: 50,
  },
  leftIcon: { marginRight: -2 },
  input: {
    flex: 1,
    fontFamily: fonts.medium,
    fontSize: 14,
    height: '100%',
    paddingVertical: 0,
  },
  placeholder: {
    flex: 1,
    fontFamily: fonts.medium,
    fontSize: 14,
  },
  rightIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
