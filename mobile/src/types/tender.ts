/**
 * Models mirror the live API exactly (see /openapi.json → components.schemas).
 * Nullable fields are nullable in the API, so the UI must handle null.
 */

export type TenderCategory = 'Works' | 'Goods' | 'Consultancy' | 'Services' | 'Other';

export type TenderStatus = 'open' | 'closed' | 'cancelled' | 'awarded';

export type VerificationStatus = 'pending' | 'verified' | 'rejected';

export interface TenderDocument {
  id: number;
  label: string;
  url: string;
  document_type: string;
  source_url: string | null;
  file_format?: string | null;
  file_size_bytes?: number | null;
  published_date?: string | null;
  download_status?: string | null;
  content_type?: string | null;
  last_checked_at?: string | null;
  is_public?: boolean | null;
  discovered_at?: string | null;
  http_status?: number | null;
  is_available?: boolean | null;
  checked_count?: number | null;
  // Added by the API's document payloads (list/detail endpoints).
  tender_id?: number;
  tender_title?: string | null;
  tender_notice_number?: string | null;
  source_name?: string | null;
  preview_url?: string;
  download_url?: string;
  viewer_url?: string;
  availability?: string;
  previewable?: boolean;
  original_url?: string;
}

export interface Tender {
  id: number;
  title: string;
  notice_number: string | null;
  organization_name: string;
  category: string;
  province: string | null;
  district: string | null;
  municipality?: string | null;
  description: string | null;
  published_date: string | null;
  deadline: string | null;
  bid_opening_date?: string | null;
  estimated_budget_npr: number | null;
  bid_security_npr?: number | null;
  notice_type?: string | null;
  procurement_type?: string | null;
  ministry?: string | null;
  department?: string | null;
  contact_info?: string | null;
  source_name: string;
  source_url: string | null;
  document_url: string | null;
  documents?: TenderDocument[] | null;
  status: string;
  verification_status: string;
  created_at: string;
  updated_at: string;
}

export interface TenderPage {
  items: Tender[];
  total: number;
  page: number;
  page_size: number;
}

export interface TenderFilters {
  q: string;
  category: string | null;
  procurementType: string | null;
  province: string | null;
  district: string | null;
  municipality: string | null;
  organization: string | null;
  ministry: string | null;
  source: string | null;
  status: string | null;
  verificationStatus: VerificationStatus | null;
  hasDocuments: boolean | null;
}

export type SortKey = 'newest' | 'closing' | 'oldest' | 'organization';

export interface FeedQuery {
  filters: TenderFilters;
  sort: SortKey;
  endpoint: 'all' | 'verified';
}

export type TenderFeedStatus = 'idle' | 'loading' | 'refreshing' | 'loadingMore' | 'ready' | 'error';

export const EMPTY_FILTERS: TenderFilters = {
  q: '',
  category: null,
  procurementType: null,
  province: null,
  district: null,
  municipality: null,
  organization: null,
  ministry: null,
  source: null,
  status: null,
  verificationStatus: null,
  hasDocuments: null,
};

export function countActiveFilters(filters: TenderFilters, includeQuery = false): number {
  let count = 0;
  if (includeQuery && filters.q.trim()) count += 1;
  if (filters.category) count += 1;
  if (filters.procurementType) count += 1;
  if (filters.province) count += 1;
  if (filters.district) count += 1;
  if (filters.municipality) count += 1;
  if (filters.organization) count += 1;
  if (filters.ministry) count += 1;
  if (filters.source) count += 1;
  if (filters.status) count += 1;
  if (filters.verificationStatus) count += 1;
  if (filters.hasDocuments) count += 1;
  return count;
}
