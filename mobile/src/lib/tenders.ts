import { CLOSING_SOON_DAYS } from '@/config';
import type { SortKey, Tender, TenderDocument } from '@/types/tender';
import { daysUntil, fileExtension, fileNameFromUrl } from '@/lib/format';

export function isOpenTender(tender: Tender): boolean {
  if (tender.status && tender.status.toLowerCase() !== 'open') return false;
  const days = daysUntil(tender.deadline);
  if (days !== null && days < 0) return false;
  return true;
}

export function isClosingSoon(tender: Tender, withinDays = CLOSING_SOON_DAYS): boolean {
  const days = daysUntil(tender.deadline);
  if (days === null) return false;
  return days >= 0 && days <= withinDays && tender.status?.toLowerCase() === 'open';
}

export function isVerified(tender: Tender): boolean {
  return tender.verification_status?.toLowerCase() === 'verified';
}

export function isPending(tender: Tender): boolean {
  return tender.verification_status?.toLowerCase() === 'pending';
}

function normalise(value: string | null | undefined): string {
  return (value ?? '')
    .toString()
    .toLowerCase()
    .replace(/[\s\-–—_.()/]+/g, ' ')
    .trim();
}

/**
 * Duplicate protection. Records are unique by id, and notices that describe
 * the same opportunity (same notice number, or same title + organisation +
 * source) are collapsed so the feed never shows the same tender twice.
 */
export function dedupeTenders(items: Tender[]): Tender[] {
  const seenIds = new Set<number>();
  const seenKeys = new Set<string>();
  const result: Tender[] = [];
  for (const tender of items) {
    if (seenIds.has(tender.id)) continue;
    const composite = tender.notice_number
      ? `notice:${normalise(tender.notice_number)}`
      : `text:${normalise(tender.title)}|${normalise(tender.organization_name)}|${normalise(
          tender.source_url,
        )}|${tender.deadline ?? ''}`;
    if (composite.length > 8 && seenKeys.has(composite)) continue;
    seenIds.add(tender.id);
    if (composite.length > 8) seenKeys.add(composite);
    result.push(tender);
  }
  return result;
}

function timestamp(value: string | null | undefined): number {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

export function sortTenders(items: Tender[], sort: SortKey): Tender[] {
  const copy = [...items];
  if (sort === 'newest') {
    copy.sort((a, b) => {
      const aDate = timestamp(a.published_date) || timestamp(a.created_at);
      const bDate = timestamp(b.published_date) || timestamp(b.created_at);
      if (bDate !== aDate) return bDate - aDate;
      return b.id - a.id;
    });
    return copy;
  }
  if (sort === 'oldest') {
    copy.sort((a, b) => {
      const aDate = timestamp(a.published_date) || timestamp(a.created_at);
      const bDate = timestamp(b.published_date) || timestamp(b.created_at);
      if (aDate !== bDate) return aDate - bDate;
      return a.id - b.id;
    });
    return copy;
  }
  // Closing soon: earliest deadline first, notices without a deadline last.
  copy.sort((a, b) => {
    const aTime = timestamp(a.deadline);
    const bTime = timestamp(b.deadline);
    if (aTime && bTime) {
      if (aTime !== bTime) return aTime - bTime;
      return b.id - a.id;
    }
    if (aTime) return -1;
    if (bTime) return 1;
    return b.id - a.id;
  });
  return copy;
}

/** Every real document URL returned by the API, de-duplicated. */
export function documentsFor(tender: Tender): TenderDocument[] {
  const documents = Array.isArray(tender.documents) ? tender.documents : [];
  const list = documents.filter((doc) => doc && typeof doc.url === 'string' && doc.url.length > 0);
  const urls = new Set(list.map((doc) => doc.url));
  if (tender.document_url && !urls.has(tender.document_url)) {
    list.push({
      id: -1,
      label: 'Tender notice',
      url: tender.document_url,
      document_type: fileExtension(tender.document_url) ?? 'Document',
      source_url: tender.source_url,
      file_format: fileExtension(tender.document_url) ?? null,
      download_status: 'unverified',
    });
    urls.add(tender.document_url);
  }
  return list.map((doc, index) => ({
    ...doc,
    id: doc.id ?? -(index + 1),
    label: doc.label?.trim() || fileNameFromUrl(doc.url),
  }));
}

export function hasDocuments(tender: Tender): boolean {
  return documentsFor(tender).length > 0;
}

export interface Facet {
  value: string;
  count: number;
}

function buildFacet(values: (string | null | undefined)[]): Facet[] {
  const counts = new Map<string, { label: string; count: number }>();
  for (const raw of values) {
    const label = (raw ?? '').trim();
    if (!label) continue;
    const key = label.toLowerCase();
    const existing = counts.get(key);
    if (existing) existing.count += 1;
    else counts.set(key, { label, count: 1 });
  }
  return Array.from(counts.values())
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
    .map((entry) => ({ value: entry.label, count: entry.count }));
}

export function deriveFacets(items: Tender[]) {
  return {
    categories: buildFacet(items.map((item) => item.category)),
    provinces: buildFacet(items.map((item) => item.province)),
    districts: buildFacet(items.map((item) => item.district)),
    municipalities: buildFacet(items.map((item) => item.municipality)),
    organizations: buildFacet(items.map((item) => item.organization_name)),
    sources: buildFacet(items.map((item) => item.source_name)),
  };
}

/** Display label for the procuring entity when the source has not identified it. */
export function organisationDisplayName(tender: Tender): string {
  const name = (tender.organization_name ?? '').trim();
  if (!name) return 'Procuring entity not published';
  if (/^not identified/i.test(name)) return 'Procuring entity pending review';
  return name;
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return 'Unknown';
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function verificationLabel(status: string | null | undefined): string {
  switch ((status ?? '').toLowerCase()) {
    case 'verified':
      return 'Verified';
    case 'pending':
      return 'Pending';
    case 'rejected':
      return 'Rejected';
    default:
      return 'Unverified';
  }
}

/** Source grouping used on the Government sources screen. */
export const SOURCE_GROUPS: { key: string; title: string; description: string; keywords: RegExp }[] = [
  {
    key: 'ppmo',
    title: 'PPMO & central procurement',
    description: 'Public Procurement Monitoring Office and central procurement notices.',
    keywords: /ppmo|public procurement monitoring|central/i,
  },
  {
    key: 'electricity',
    title: 'Electricity & energy',
    description: 'Utility and energy-sector procuring entities.',
    keywords: /electricity|\bnea\b|energy|power|विद्युत|hydro/i,
  },
  {
    key: 'roads',
    title: 'Roads & transportation',
    description: 'Road, bridge and transport agencies.',
    keywords: /road|transport|traffic|highway|सडक|यातायात/i,
  },
  {
    key: 'water',
    title: 'Water supply & irrigation',
    description: 'Drinking water, sanitation and irrigation offices.',
    keywords: /water|irrigation|खानेपानी|सिँचाइ|सिंचाइ|jal|dwssm/i,
  },
  {
    key: 'metropolitan',
    title: 'Metropolitan & sub-metropolitan cities',
    description: 'Metropolitan city procurement offices.',
    keywords: /metropolitan city|sub-metropolitan|महानगर/i,
  },
  {
    key: 'municipalities',
    title: 'Municipalities',
    description: 'Municipal governments publishing local notices.',
    keywords: /municipality|नगरपालिका|nagarpalika/i,
  },
  {
    key: 'rural',
    title: 'Rural municipalities',
    description: 'Rural municipal procurement notices.',
    keywords: /rural municipality|गाउँपालिका|gaunpalika/i,
  },
  {
    key: 'urban',
    title: 'Urban development & construction',
    description: 'Urban development, building and construction agencies.',
    keywords: /urban|construction|building|निर्माण|विकास/i,
  },
  {
    key: 'ministries',
    title: 'Ministries & departments',
    description: 'Ministries, departments, division offices and directorates.',
    keywords: /ministry|department|division|directorate|office|कार्यालय|मन्त्रालय|विभाग/i,
  },
  {
    key: 'infrastructure',
    title: 'Infrastructure agencies',
    description: 'Authorities, boards and infrastructure programmes.',
    keywords: /authority|board|infrastructure|project|आयोजना|समिति/i,
  },
];

export function groupSources(sources: Facet[]) {
  const groups = SOURCE_GROUPS.map((group) => ({
    ...group,
    sources: [] as Facet[],
  }));
  const other: Facet[] = [];
  for (const source of sources) {
    const group = groups.find((entry) => entry.keywords.test(source.value));
    if (group) group.sources.push(source);
    else other.push(source);
  }
  const filled = groups.filter((group) => group.sources.length > 0);
  if (other.length > 0) {
    filled.push({
      key: 'other',
      title: 'Other published sources',
      description: 'Sources that do not match a standard category yet.',
      keywords: /$^/,
      sources: other,
    });
  }
  return filled;
}
