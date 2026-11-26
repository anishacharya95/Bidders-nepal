import { Ionicons } from '@expo/vector-icons';
import { useEffect, useMemo, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText } from '@/components/ui/app-text';
import { Button } from '@/components/ui/button';
import { Chip } from '@/components/ui/chip';
import { countActiveFilters, EMPTY_FILTERS, type TenderFilters } from '@/types/tender';
import type { Facet } from '@/lib/tenders';
import { useAppTheme } from '@/providers/theme-provider';
import { fonts, maxContentWidth, radii, spacing } from '@/theme';

const STATUS_OPTIONS = [
  { value: 'active', label: 'Open now' },
  { value: 'closed', label: 'Closed' },
  { value: 'expired', label: 'Expired' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'awarded', label: 'Awarded' },
];

const PROCUREMENT_TYPES = [
  'Goods',
  'Works',
  'Consulting Services',
  'Non-consulting Services',
];

const VERIFICATION_OPTIONS = [
  { value: 'verified', label: 'Verified' },
  { value: 'pending', label: 'Pending' },
];

const CATEGORY_FALLBACK = ['Works', 'Goods', 'Consultancy', 'Services', 'Other'];

interface FilterSheetProps {
  visible: boolean;
  filters: TenderFilters;
  categories: Facet[];
  procurementTypes?: Facet[];
  ministries?: Facet[];
  provinces: Facet[];
  districts: Facet[];
  municipalities: Facet[];
  organizations: Facet[];
  sources?: Facet[];
  onClose: () => void;
  onApply: (filters: TenderFilters) => void;
}

export function FilterSheet({
  visible,
  filters,
  categories,
  procurementTypes = [],
  ministries = [],
  provinces,
  districts,
  municipalities,
  organizations,
  sources = [],
  onClose,
  onApply,
}: FilterSheetProps) {
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const [draft, setDraft] = useState<TenderFilters>(filters);
  const [districtQuery, setDistrictQuery] = useState('');
  const [municipalityQuery, setMunicipalityQuery] = useState('');
  const [organizationQuery, setOrganizationQuery] = useState('');
  const [sourceQuery, setSourceQuery] = useState('');

  useEffect(() => {
    if (visible) {
      setDraft(filters);
      setDistrictQuery('');
      setMunicipalityQuery('');
      setOrganizationQuery('');
    }
  }, [visible, filters]);

  const categoryOptions = useMemo(() => {
    if (categories.length === 0) {
      return CATEGORY_FALLBACK.map((value) => ({ value, count: 0 }));
    }
    return categories;
  }, [categories]);

  const visibleDistricts = useMemo(() => {
    const query = districtQuery.trim().toLowerCase();
    const list = query
      ? districts.filter((item) => item.value.toLowerCase().includes(query))
      : districts;
    return list.slice(0, 40);
  }, [districtQuery, districts]);

  const visibleMunicipalities = useMemo(() => {
    const query = municipalityQuery.trim().toLowerCase();
    const list = query
      ? municipalities.filter((item) => item.value.toLowerCase().includes(query))
      : municipalities;
    return list.slice(0, 40);
  }, [municipalityQuery, municipalities]);

  const visibleOrganizations = useMemo(() => {
    const query = organizationQuery.trim().toLowerCase();
    const list = query
      ? organizations.filter((item) => item.value.toLowerCase().includes(query))
      : organizations;
    return list.slice(0, 25);
  }, [organizationQuery, organizations]);

  const visibleSources = useMemo(() => {
    const query = sourceQuery.trim().toLowerCase();
    const list = query
      ? sources.filter((item) => item.value.toLowerCase().includes(query))
      : sources;
    return list.slice(0, 25);
  }, [sourceQuery, sources]);

  const procurementOptions = useMemo(() => {
    if (procurementTypes.length === 0) {
      return PROCUREMENT_TYPES.map((value) => ({ value, count: 0 }));
    }
    return procurementTypes;
  }, [procurementTypes]);

  const toggle = (key: keyof TenderFilters, value: string | null) => {
    setDraft((current) => ({ ...current, [key]: current[key] === value ? null : value }));
  };

  const resetAll = () => setDraft({ ...EMPTY_FILTERS, q: draft.q });

  const activeCount = countActiveFilters(draft);

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={[styles.backdrop, { backgroundColor: colors.overlay }]}>
        <Pressable style={styles.backdropPress} onPress={onClose} accessibilityLabel="Close filters" />
        <View
          style={[
            styles.sheet,
            {
              backgroundColor: colors.background,
              borderColor: colors.border,
              paddingBottom: Math.max(insets.bottom, spacing.md),
            },
          ]}>
          <View style={styles.handleWrap}>
            <View style={[styles.handle, { backgroundColor: colors.borderStrong }]} />
          </View>

          <View style={styles.header}>
            <View>
              <AppText variant="h2">Filters</AppText>
              <AppText variant="caption" color="textTertiary">
                {activeCount === 0 ? 'No filters applied' : `${activeCount} filter${activeCount === 1 ? '' : 's'} applied`}
              </AppText>
            </View>
            <Button
              label="Reset"
              variant="ghost"
              size="sm"
              icon="refresh"
              onPress={resetAll}
            />
          </View>

          <ScrollView
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}>
            <FilterGroup title="Tender status">
              <Chip label="All" selected={!draft.status} onPress={() => toggle('status', null)} />
              {STATUS_OPTIONS.map((option) => (
                <Chip
                  key={option.value}
                  label={option.label}
                  selected={draft.status === option.value}
                  onPress={() => toggle('status', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup title="Verification">
              <Chip
                label="All"
                selected={!draft.verificationStatus}
                onPress={() => toggle('verificationStatus', null)}
              />
              {VERIFICATION_OPTIONS.map((option) => (
                <Chip
                  key={option.value}
                  label={option.label}
                  selected={draft.verificationStatus === option.value}
                  onPress={() => toggle('verificationStatus', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup title="Bid documents">
              <Chip
                label="All notices"
                selected={draft.hasDocuments === null}
                onPress={() => setDraft((current) => ({ ...current, hasDocuments: null }))}
              />
              <Chip
                label="With documents"
                icon="document-text-outline"
                selected={draft.hasDocuments === true}
                onPress={() => setDraft((current) => ({ ...current, hasDocuments: true }))}
              />
              <Chip
                label="No documents"
                icon="document-outline"
                selected={draft.hasDocuments === false}
                onPress={() => setDraft((current) => ({ ...current, hasDocuments: false }))}
              />
            </FilterGroup>

            <FilterGroup title="Procurement type">
              <Chip
                label="All"
                selected={!draft.procurementType}
                onPress={() => toggle('procurementType', null)}
              />
              {procurementOptions.map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count || undefined}
                  selected={draft.procurementType === option.value}
                  onPress={() => toggle('procurementType', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup title="Category">
              <Chip label="All" selected={!draft.category} onPress={() => toggle('category', null)} />
              {categoryOptions.map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count || undefined}
                  selected={draft.category === option.value}
                  onPress={() => toggle('category', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup
              title="Ministry"
              hint={
                ministries.length === 0
                  ? 'Ministries appear when a notice names one as the procuring entity.'
                  : undefined
              }>
              <Chip
                label="All"
                selected={!draft.ministry}
                onPress={() => toggle('ministry', null)}
              />
              {ministries.slice(0, 20).map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count}
                  selected={draft.ministry === option.value}
                  onPress={() => toggle('ministry', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup
              title="Province"
              hint={
                provinces.length === 0
                  ? 'The current feed does not report provinces yet.'
                  : undefined
              }>
              <Chip label="All" selected={!draft.province} onPress={() => toggle('province', null)} />
              {provinces.map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count}
                  selected={draft.province === option.value}
                  onPress={() => toggle('province', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup
              title="District"
              hint={districts.length === 0 ? 'No districts reported in the current feed.' : undefined}>
              <Chip label="All" selected={!draft.district} onPress={() => toggle('district', null)} />
              {districts.length > 8 ? (
                <SearchInput
                  value={districtQuery}
                  onChangeText={setDistrictQuery}
                  placeholder="Find a district"
                />
              ) : null}
              {visibleDistricts.map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count}
                  selected={draft.district === option.value}
                  onPress={() => toggle('district', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup
              title="Municipality"
              hint={
                municipalities.length === 0
                  ? 'No municipalities reported in the current feed.'
                  : undefined
              }>
              <Chip
                label="All"
                selected={!draft.municipality}
                onPress={() => toggle('municipality', null)}
              />
              {municipalities.length > 8 ? (
                <SearchInput
                  value={municipalityQuery}
                  onChangeText={setMunicipalityQuery}
                  placeholder="Find a municipality"
                />
              ) : null}
              {visibleMunicipalities.map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count}
                  selected={draft.municipality === option.value}
                  onPress={() => toggle('municipality', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup
              title="Organization"
              hint={
                organizations.length === 0
                  ? 'No organisations reported in the current feed.'
                  : undefined
              }>
              <Chip
                label="All"
                selected={!draft.organization}
                onPress={() => toggle('organization', null)}
              />
              {organizations.length > 8 ? (
                <SearchInput
                  value={organizationQuery}
                  onChangeText={setOrganizationQuery}
                  placeholder="Find an organisation"
                />
              ) : null}
              {visibleOrganizations.map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count}
                  selected={draft.organization === option.value}
                  onPress={() => toggle('organization', option.value)}
                />
              ))}
            </FilterGroup>

            <FilterGroup
              title="Source website"
              hint={
                sources.length === 0
                  ? 'No sources reported in the current feed.'
                  : undefined
              }>
              <Chip label="All" selected={!draft.source} onPress={() => toggle('source', null)} />
              {sources.length > 8 ? (
                <SearchInput
                  value={sourceQuery}
                  onChangeText={setSourceQuery}
                  placeholder="Find a source website"
                />
              ) : null}
              {visibleSources.map((option) => (
                <Chip
                  key={option.value}
                  label={option.value}
                  count={option.count}
                  selected={draft.source === option.value}
                  onPress={() => toggle('source', option.value)}
                />
              ))}
            </FilterGroup>

            <AppText variant="caption" color="textTertiary" style={styles.note}>
              Filter options are built from notices currently returned by the Bidders Nepal API.
            </AppText>
          </ScrollView>

          <View style={[styles.footer, { borderTopColor: colors.border }]}>
            <Button
              label="Clear all"
              variant="secondary"
              onPress={resetAll}
              style={styles.footerButton}
            />
            <Button
              label="Show results"
              icon="checkmark"
              onPress={() => {
                onApply(draft);
                onClose();
              }}
              style={styles.footerButton}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

function FilterGroup({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.group}>
      <AppText variant="label" color="textTertiary">
        {title}
      </AppText>
      {hint ? (
        <AppText variant="caption" color="textTertiary">
          {hint}
        </AppText>
      ) : null}
      <View style={styles.chips}>{children}</View>
    </View>
  );
}

function SearchInput({
  value,
  onChangeText,
  placeholder,
}: {
  value: string;
  onChangeText: (value: string) => void;
  placeholder: string;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.searchInput, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <Ionicons name="search" size={14} color={colors.textTertiary} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textTertiary}
        style={[styles.searchText, { color: colors.text }]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdropPress: {
    flex: 1,
  },
  sheet: {
    borderTopLeftRadius: radii.xxl,
    borderTopRightRadius: radii.xxl,
    borderWidth: 1,
    maxHeight: '90%',
    width: '100%',
    maxWidth: maxContentWidth + 80,
    alignSelf: 'center',
  },
  handleWrap: {
    alignItems: 'center',
    paddingTop: spacing.md,
  },
  handle: {
    width: 42,
    height: 4,
    borderRadius: 2,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  scroll: {
    paddingHorizontal: spacing.xl,
  },
  scrollContent: {
    gap: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.xl,
  },
  group: {
    gap: spacing.sm,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    alignItems: 'center',
  },
  searchInput: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 38,
    borderRadius: radii.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    width: '100%',
  },
  searchText: {
    flex: 1,
    fontFamily: fonts.medium,
    fontSize: 13,
    paddingVertical: 0,
  },
  note: {
    marginTop: spacing.sm,
  },
  footer: {
    flexDirection: 'row',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    borderTopWidth: 1,
  },
  footerButton: {
    flex: 1,
  },
});
