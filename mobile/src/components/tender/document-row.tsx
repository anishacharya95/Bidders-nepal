import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { downloadDocument, downloadDocumentById, shareDocument } from '@/lib/documents';
import { documentTypeLabel, fileNameFromUrl, formatDate } from '@/lib/format';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';
import type { TenderDocument } from '@/types/tender';

const PREVIEWABLE = new Set(['PDF', 'JPG', 'JPEG', 'PNG', 'TXT', 'CSV']);

function availabilityTone(doc: TenderDocument) {
  if (doc.is_available === true) return 'success' as const;
  if (doc.availability === 'restricted') return 'warning' as const;
  if (doc.is_available === false) return 'danger' as const;
  return 'neutral' as const;
}

function availabilityLabel(doc: TenderDocument): string {
  if (doc.is_available === true) return 'Available';
  if (doc.availability === 'restricted') return 'Restricted';
  if (doc.availability === 'missing') return 'Removed';
  if (doc.is_available === false) return 'Unreachable';
  if (doc.download_status === 'available') return 'Available';
  return 'Not checked';
}

export function DocumentRow({
  document: doc,
  tenderTitle,
}: {
  document: TenderDocument;
  tenderTitle: string;
}) {
  const { colors } = useAppTheme();
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<'open' | 'download' | null>(null);

  const type = documentTypeLabel(doc.document_type, doc.url);
  const fileName = fileNameFromUrl(doc.url);
  const format = (doc.file_format || '').toUpperCase();
  const previewable = doc.previewable ?? PREVIEWABLE.has(format);
  const size =
    typeof doc.file_size_bytes === 'number' && doc.file_size_bytes > 0
      ? doc.file_size_bytes >= 1024 * 1024
        ? `${(doc.file_size_bytes / (1024 * 1024)).toFixed(1)} MB`
        : `${Math.max(1, Math.round(doc.file_size_bytes / 1024))} KB`
      : null;
  const published = formatDate(doc.published_date ?? doc.discovered_at ?? null);
  const meta = [format || null, size, published ? `added ${published}` : null]
    .filter(Boolean)
    .join(' · ');

  const run = async (action: 'open' | 'download' | 'share') => {
    setMessage(null);
    if (action === 'share') {
      const result = await shareDocument(doc, tenderTitle);
      if (!result.ok) setMessage(result.message ?? null);
      return;
    }

    if (action === 'open') {
      if (previewable && doc.id > 0) {
        // In-app reader: PDF.js inside the app, no external browser redirect.
        router.push({
          pathname: '/document/[id]',
          params: {
            id: String(doc.id),
            title: doc.label,
            format: format || 'PDF',
          },
        });
        return;
      }
      if (!previewable && doc.id > 0) {
        setBusy('open');
        const result = await downloadDocumentById(doc.id, doc.label, doc.file_format);
        setBusy(null);
        setMessage(
          result.message ??
            'This format cannot be previewed in the app. The file was opened with your device viewer.',
        );
        return;
      }
    }

    setBusy('download');
    const result =
      doc.id > 0 && doc.previewable !== undefined
        ? await downloadDocumentById(doc.id, doc.label, doc.file_format)
        : await downloadDocument(doc);
    setBusy(null);
    if (!result.ok || result.message) setMessage(result.message ?? null);
  };

  return (
    <View style={[styles.row, { borderColor: colors.border, backgroundColor: colors.surface }]}>
      <View style={styles.top}>
        <View style={[styles.fileIcon, { backgroundColor: colors.navySoft }]}>
          <Ionicons name="document-text" size={19} color={colors.navy} />
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
          <View style={styles.badgeRow}>
            <Badge label={availabilityLabel(doc)} tone={availabilityTone(doc)} dot />
            {previewable ? <Badge label="In-app preview" tone="info" icon="eye-outline" /> : null}
          </View>
          {message ? (
            <AppText variant="caption" color="textSecondary" style={styles.message}>
              {message}
            </AppText>
          ) : null}
        </View>
      </View>
      <View style={styles.actions}>
        <ActionButton
          label={busy === 'open' ? 'Opening…' : previewable ? 'View' : 'Open'}
          icon={previewable ? 'eye-outline' : 'open-outline'}
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
    gap: 3,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 2,
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
