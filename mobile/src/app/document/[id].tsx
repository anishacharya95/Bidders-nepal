import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useRef, useState, type ComponentRef } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';

import {
  documentViewerUrl,
  fetchDocumentMeta,
  fetchDocumentStatus,
  type DocumentStatus,
} from '@/api/tenders';
import { AppText } from '@/components/ui/app-text';
import { Badge } from '@/components/ui/badge';
import { Button, IconButton } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { EmptyState, ErrorState, InlineNotice } from '@/components/ui/states';
import { downloadDocumentById, shareDocument } from '@/lib/documents';
import { formatDate } from '@/lib/format';
import { useAppTheme } from '@/providers/theme-provider';
import { radii, spacing } from '@/theme';
import type { TenderDocument } from '@/types/tender';

type ViewerState = 'loading' | 'ready' | 'error';

function availabilityTone(status: DocumentStatus | null) {
  if (!status) return 'neutral' as const;
  if (status.isAvailable === true) return 'success' as const;
  if (status.availability === 'restricted') return 'warning' as const;
  if (status.isAvailable === false) return 'danger' as const;
  return 'neutral' as const;
}

function availabilityLabel(status: DocumentStatus | null): string {
  if (!status) return 'Checking availability';
  if (status.isAvailable === true) return 'Available at source';
  if (status.availability === 'restricted') return 'Restricted by source';
  if (status.availability === 'missing') return 'Removed from source';
  if (status.isAvailable === false) return 'Not reachable';
  return 'Not checked yet';
}

/**
 * In-app PDF reader. The page is rendered by the API's own PDF.js viewer over
 * HTTPS, so page navigation, zoom, text search and full screen all work without
 * leaving Bidders Nepal (and without a third-party viewer seeing the request).
 */
export default function DocumentViewerScreen() {
  const params = useLocalSearchParams<{ id: string; title?: string; format?: string }>();
  const documentId = Number(params.id);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { colors } = useAppTheme();

  const [document, setDocument] = useState<TenderDocument | null>(null);
  const [status, setStatus] = useState<DocumentStatus | null>(null);
  const [state, setState] = useState<ViewerState>('loading');
  const [message, setMessage] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState<'download' | 'share' | null>(null);
  const webviewRef = useRef<ComponentRef<typeof WebView>>(null);

  useEffect(() => {
    if (!Number.isFinite(documentId)) {
      setState('error');
      setMessage('This document link is invalid.');
      return;
    }
    let active = true;
    const controller = new AbortController();
    setState('loading');
    setMessage(null);

    fetchDocumentStatus(documentId, controller.signal)
      .then((result) => {
        if (active) setStatus(result);
      })
      .catch(() => undefined);
    fetchDocumentMeta(documentId, controller.signal)
      .then((meta) => {
        if (active && meta) setDocument(meta);
      })
      .catch(() => undefined);

    return () => {
      active = false;
      controller.abort();
    };
  }, [documentId, attempt]);

  const onDownload = useCallback(async () => {
    if (!document) return;
    setBusy('download');
    const result = await downloadDocumentById(
      document.id,
      document.label,
      document.file_format,
    );
    setBusy(null);
    if (result.message) setMessage(result.message);
  }, [document]);

  const onShare = useCallback(async () => {
    if (!document) return;
    setBusy('share');
    const result = await shareDocument(document);
    setBusy(null);
    if (!result.ok) setMessage(result.message ?? null);
  }, [document]);

  const onOriginal = useCallback(async () => {
    if (!document?.url) return;
    const result = await WebBrowser.openBrowserAsync(document.url);
    if (result.type === 'cancel') return;
  }, [document]);

  if (!Number.isFinite(documentId)) {
    return (
      <Screen>
        <View style={styles.topBar}>
          <IconButton icon="arrow-back" variant="surface" onPress={() => router.back()} />
        </View>
        <View style={styles.body}>
          <ErrorState title="Invalid document" message="This document link is invalid." />
        </View>
      </Screen>
    );
  }

  const format = (document?.file_format || params.format || '').toUpperCase();
  const isPdf = format === 'PDF' || !format;
  const title = document?.label || params.title || 'Bid document';

  return (
    <Screen style={styles.screen}>
      <View style={[styles.topBar, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton icon="arrow-back" variant="surface" onPress={() => router.back()} />
        <View style={styles.titleWrap}>
          <AppText variant="smallStrong" numberOfLines={1}>
            {title}
          </AppText>
          <View style={styles.metaRow}>
            <Badge
              label={availabilityLabel(status)}
              tone={availabilityTone(status)}
              dot
            />
            {format ? <AppText variant="caption" color="textTertiary">{format}</AppText> : null}
            {document?.file_size_bytes ? (
              <AppText variant="caption" color="textTertiary">
                {document.file_size_bytes >= 1024 * 1024
                  ? `${(document.file_size_bytes / (1024 * 1024)).toFixed(1)} MB`
                  : `${Math.max(1, Math.round(document.file_size_bytes / 1024))} KB`}
              </AppText>
            ) : null}
          </View>
        </View>
        <Pressable
          onPress={() => setAttempt((value) => value + 1)}
          accessibilityLabel="Retry loading the document"
          style={styles.iconButton}>
          <Ionicons name="refresh" size={18} color={colors.textSecondary} />
        </Pressable>
      </View>

      {!isPdf ? (
        <View style={styles.body}>
          <InlineNotice
            tone="info"
            icon="document-outline"
            title={`${format || 'This format'} opens as a download`}
            message="Word, Excel and archive files cannot be previewed safely inside the app. Download the file, or open the original source to read it there."
          />
          <View style={styles.actions}>
            <Button
              label={busy === 'download' ? 'Downloading…' : 'Download document'}
              icon="download-outline"
              onPress={onDownload}
              loading={busy === 'download'}
            />
            <Button label="Share" icon="share-outline" variant="secondary" onPress={onShare} />
            <Button
              label="Open original source"
              icon="open-outline"
              variant="ghost"
              onPress={onOriginal}
            />
          </View>
          {message ? (
            <AppText variant="caption" color="textSecondary">
              {message}
            </AppText>
          ) : null}
        </View>
      ) : null}

      {isPdf ? (
        <View style={styles.viewerWrap}>
          {state === 'loading' ? (
            <View style={styles.center}>
              <ActivityIndicator color={colors.navy} />
              <AppText variant="caption" color="textTertiary" style={{ marginTop: spacing.sm }}>
                Opening the document…
              </AppText>
            </View>
          ) : null}

          {state === 'error' ? (
            <View style={styles.body}>
              <EmptyState
                icon="cloud-offline-outline"
                title="This document could not be opened"
                message={
                  message ??
                  'The source did not return the file. It may have been moved, replaced or taken offline.'
                }
                actionLabel="Try again"
                onAction={() => {
                  setAttempt((value) => value + 1);
                  webviewRef.current?.reload();
                }}
              />
              <View style={styles.actions}>
                <Button
                  label={busy === 'download' ? 'Downloading…' : 'Download instead'}
                  icon="download-outline"
                  variant="secondary"
                  onPress={onDownload}
                  loading={busy === 'download'}
                />
                <Button label="Open original source" icon="open-outline" variant="ghost" onPress={onOriginal} />
              </View>
            </View>
          ) : (
            <WebView
              ref={webviewRef}
              key={`${documentId}-${attempt}`}
              source={{ uri: documentViewerUrl(documentId) }}
              originWhitelist={['*']}
              javaScriptEnabled
              domStorageEnabled
              allowsFullscreenVideo
              setBuiltInZoomControls={false}
              style={[styles.webview, state === 'loading' && styles.hidden]}
              onLoadStart={() => setState('loading')}
              onLoadEnd={() => setState((current) => (current === 'error' ? current : 'ready'))}
              onError={(event: { nativeEvent: { description?: string } }) => {
                setState('error');
                setMessage(
                  event.nativeEvent.description ||
                    'The document viewer could not load this file.',
                );
              }}
              onHttpError={(event: { nativeEvent: { statusCode: number } }) => {
                if (event.nativeEvent.statusCode >= 400) {
                  setState('error');
                  setMessage(
                    `The document could not be streamed (HTTP ${event.nativeEvent.statusCode}).`,
                  );
                }
              }}
            />
          )}
        </View>
      ) : null}

      <View
        style={[
          styles.footer,
          {
            backgroundColor: colors.surface,
            borderTopColor: colors.border,
            paddingBottom: Math.max(insets.bottom, spacing.sm),
          },
        ]}>
        <Button
          label={busy === 'download' ? 'Saving…' : 'Download'}
          icon="download-outline"
          size="sm"
          variant="secondary"
          onPress={onDownload}
          loading={busy === 'download'}
          style={styles.footerButton}
        />
        <Button
          label="Share"
          icon="share-outline"
          size="sm"
          variant="secondary"
          onPress={onShare}
          loading={busy === 'share'}
          style={styles.footerButton}
        />
        <Button
          label="Original"
          icon="open-outline"
          size="sm"
          variant="ghost"
          onPress={onOriginal}
          style={styles.footerButton}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  titleWrap: {
    flex: 1,
    gap: 3,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  iconButton: {
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
  },
  viewerWrap: {
    flex: 1,
  },
  webview: {
    flex: 1,
    backgroundColor: '#0B1F3A',
  },
  hidden: {
    opacity: 0,
  },
  screen: {
    paddingHorizontal: 0,
  },
  center: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },
  body: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  actions: {
    gap: spacing.sm,
  },
  footer: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
  },
  footerButton: {
    flex: 1,
  },
});
