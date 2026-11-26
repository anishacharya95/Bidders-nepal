import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { openDocument, downloadDocument, shareDocument } from '@/lib/documents';
import { documentTypeLabel, fileNameFromUrl } from '@/lib/format';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';
import type { TenderDocument } from '@/types/tender';

export function DocumentRow({
  document: doc,
  tenderTitle,
}: {
  document: TenderDocument;
  tenderTitle: string;
}) {
  const { colors } = useAppTheme();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<'open' | 'download' | null>(null);
  const type = documentTypeLabel(doc.document_type, doc.url);
  const fileName = fileNameFromUrl(doc.url);
  const size =
    typeof doc.file_size_bytes === 'number' && doc.file_size_bytes > 0
      ? doc.file_size_bytes >= 1024 * 1024
        ? `${(doc.file_size_bytes / (1024 * 1024)).toFixed(1)} MB`
        : `${Math.max(1, Math.round(doc.file_size_bytes / 1024))} KB`
      : null;
  const meta = [doc.file_format || null, size, doc.download_status || null]
    .filter(Boolean)
    .join(' · ');

  const run = async (action: 'open' | 'download' | 'share') => {
    setMessage(null);
    if (action === 'share') {
      const result = await shareDocument(doc, tenderTitle);
      if (!result.ok) setMessage(result.message ?? null);
      return;
    }
    setBusy(action);
    const result = action === 'open' ? await openDocument(doc.url) : await downloadDocument(doc);
    setBusy(null);
    if (!result.ok || result.message) setMessage(result.message ?? null);
  };

  return (
    <View style={[styles.row, { borderColor: colors.border, backgroundColor: colors.surface }]}>
      <View style={styles.top}>
        <View style={[styles.fileIcon, { backgroundColor: colors.dangerSoft }]}>
          <Ionicons name="document-text" size={19} color={colors.danger} />
        </View>
        <View style={styles.copy}>
          <AppText variant="smallStrong" numberOfLines={2}>
            {doc.label}
          </AppText>
          <AppText variant="caption" color="textTertiary" numberOfLines={1}>
            {type} · {fileName}
          </AppText>
          {meta ? (
            <AppText variant="caption" color="textTertiary" numberOfLines={1}>
              {meta}
            </AppText>
          ) : null}
          {message ? (
            <AppText variant="caption" color="textSecondary" style={styles.message}>
              {message}
            </AppText>
          ) : null}
        </View>
      </View>
      <View style={styles.actions}>
        <ActionButton
          label={busy === 'open' ? 'Opening…' : 'Open'}
          icon="open-outline"
          onPress={() => run('open')}
          primary
        />
        <ActionButton
          label={busy === 'download' ? 'Saving…' : 'Download'}
          icon="download-outline"
          onPress={() => run('download')}
        />
        <ActionButton label="Share" icon="share-outline" onPress={() => run('share')} />
      </View>
    </View>
  );
}

function ActionButton({
  label,
  icon,
  onPress,
  primary,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  primary?: boolean;
}) {
  const { colors } = useAppTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.action,
        {
          backgroundColor: primary ? colors.navySoft : 'transparent',
          borderColor: primary ? colors.navySoft : colors.border,
          opacity: pressed ? 0.65 : 1,
        },
      ]}>
      <Ionicons name={icon} size={13} color={primary ? colors.navy : colors.textSecondary} />
      <AppText variant="caption" color={primary ? 'navy' : 'textSecondary'}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    borderWidth: 1,
    borderRadius: radii.md,
    padding: spacing.md,
    gap: spacing.md,
  },
  top: {
    flexDirection: 'row',
    gap: spacing.md,
    alignItems: 'flex-start',
  },
  fileIcon: {
    width: 38,
    height: 38,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  copy: {
    flex: 1,
    gap: 2,
  },
  message: {
    marginTop: 4,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  action: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    height: 32,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
});
