const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | null | undefined): string | null {
  const date = parseDate(value);
  if (!date) return null;
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

export function formatDateTime(value: string | null | undefined): string | null {
  const date = parseDate(value);
  if (!date) return null;
  let hours = date.getHours();
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const suffix = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12 || 12;
  return `${formatDate(value)} · ${hours}:${minutes} ${suffix}`;
}

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** Whole days between today and the deadline (negative when past). */
export function daysUntil(value: string | null | undefined): number | null {
  const date = parseDate(value);
  if (!date) return null;
  const today = startOfDay(new Date());
  const target = startOfDay(date);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

export function remainingLabel(value: string | null | undefined): {
  label: string;
  days: number | null;
  tone: 'success' | 'warning' | 'danger' | 'neutral';
} {
  const days = daysUntil(value);
  if (days === null) return { label: 'Deadline not published', days: null, tone: 'neutral' };
  if (days < 0) {
    return {
      label: days === -1 ? 'Closed yesterday' : `Closed ${Math.abs(days)} days ago`,
      days,
      tone: 'neutral',
    };
  }
  if (days === 0) return { label: 'Closes today', days, tone: 'danger' };
  if (days === 1) return { label: '1 day left', days, tone: 'danger' };
  if (days <= 7) return { label: `${days} days left`, days, tone: 'warning' };
  return { label: `${days} days left`, days, tone: 'success' };
}

export function relativeTime(value: string | null | undefined): string | null {
  const date = parseDate(value);
  if (!date) return null;
  const diff = Date.now() - date.getTime();
  if (diff < 60_000) return 'just now';
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(value);
}

/** NPR amounts written the way Nepali procurement readers expect. */
export function formatBudget(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  if (value >= 10_000_000) {
    const crore = value / 10_000_000;
    return `NPR ${trim(crore)} crore`;
  }
  if (value >= 100_000) {
    const lakh = value / 100_000;
    return `NPR ${trim(lakh)} lakh`;
  }
  return `NPR ${Math.round(value).toLocaleString('en-US')}`;
}

function trim(value: number): string {
  return value
    .toFixed(2)
    .replace(/\.00$/, '')
    .replace(/0$/, '');
}

export function pluralise(count: number, singular: string, plural = `${singular}s`): string {
  return `${count.toLocaleString('en-US')} ${count === 1 ? singular : plural}`;
}

export function fileExtension(url: string | null | undefined): string | null {
  if (!url) return null;
  const clean = url.split(/[?#]/)[0];
  const match = clean.match(/\.([a-z0-9]{2,5})$/i);
  return match ? match[1].toUpperCase() : null;
}

export function documentTypeLabel(documentType: string | null | undefined, url: string): string {
  const declared = (documentType ?? '').trim();
  if (declared) return declared.toUpperCase();
  return fileExtension(url) ?? 'FILE';
}

export function fileNameFromUrl(url: string): string {
  try {
    const clean = url.split(/[?#]/)[0];
    const name = decodeURIComponent(clean.split('/').filter(Boolean).pop() ?? '');
    return name || 'document';
  } catch {
    return 'document';
  }
}

export function initials(value: string): string {
  const parts = value
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return 'BN';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function truncate(value: string, max = 90): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1).trimEnd()}…`;
}
