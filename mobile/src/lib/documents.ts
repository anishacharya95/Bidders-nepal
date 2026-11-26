import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import * as WebBrowser from 'expo-web-browser';
import { Linking, Platform, Share } from 'react-native';

import { fileExtension, fileNameFromUrl } from '@/lib/format';
import type { TenderDocument } from '@/types/tender';

export interface ActionResult {
  ok: boolean;
  message?: string;
}

function safeFileName(label: string, url: string): string {
  const extension = fileExtension(url)?.toLowerCase() ?? 'pdf';
  const base = (label || fileNameFromUrl(url))
    .replace(/\.[a-z0-9]{2,5}$/i, '')
    .replace(/[^\w\u0900-\u097F\- ]+/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .slice(0, 60);
  return `${base || 'bid-document'}.${extension}`;
}

/** Open the real document URL in an in-app browser sheet (native) or a tab (web). */
export async function openDocument(url: string): Promise<ActionResult> {
  try {
    if (Platform.OS === 'web') {
      await Linking.openURL(url);
      return { ok: true };
    }
    await WebBrowser.openBrowserAsync(url, {
      presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET,
      controlsColor: '#0B1F3A',
    });
    return { ok: true };
  } catch {
    return { ok: false, message: 'Could not open this document. Check your connection and retry.' };
  }
}

/** Download the document, then offer the system share/save sheet on Android. */
export async function downloadDocument(doc: TenderDocument): Promise<ActionResult> {
  try {
    if (Platform.OS === 'web') {
      await Linking.openURL(doc.url);
      return { ok: true, message: 'Opened in a new tab — use the browser save button.' };
    }

    const filename = safeFileName(doc.label, doc.url);
    const target = `${FileSystem.cacheDirectory ?? ''}${filename}`;
    const result = await FileSystem.downloadAsync(doc.url, target);
    if (!result?.uri) throw new Error('Download failed');

    if (await Sharing.isAvailableAsync()) {
      await Sharing.shareAsync(result.uri, {
        mimeType: 'application/pdf',
        dialogTitle: 'Save bid document',
        UTI: 'com.adobe.pdf',
      });
      return { ok: true, message: 'Downloaded. Choose where to save it.' };
    }
    return { ok: true, message: `Saved to ${result.uri}` };
  } catch {
    return {
      ok: false,
      message: 'This document could not be downloaded. You can still open it in the browser.',
    };
  }
}

export async function shareDocument(doc: TenderDocument, tenderTitle?: string): Promise<ActionResult> {
  try {
    const title = tenderTitle ? `${tenderTitle}\n` : '';
    await Share.share({
      message: `${title}${doc.label}: ${doc.url}`,
      url: doc.url,
      title: doc.label,
    });
    return { ok: true };
  } catch {
    return { ok: false, message: 'Sharing was cancelled.' };
  }
}

export async function shareTenderLink(url: string, title: string): Promise<ActionResult> {
  try {
    await Share.share({ message: `${title}\n${url}`, url, title });
    return { ok: true };
  } catch {
    return { ok: false, message: 'Sharing was cancelled.' };
  }
}
