import { useEffect, useState } from 'react';

import { fetchAllTenders } from '@/api/tenders';
import { MAX_PAGE_SIZE } from '@/config';
import { deriveFacets, type Facet } from '@/lib/tenders';
import { EMPTY_FILTERS } from '@/types/tender';

interface Facets {
  categories: Facet[];
  provinces: Facet[];
  districts: Facet[];
  municipalities: Facet[];
  organizations: Facet[];
  sources: Facet[];
  noticeCount: number;
}

const emptyFacets: Facets = {
  categories: [],
  provinces: [],
  districts: [],
  municipalities: [],
  organizations: [],
  sources: [],
  noticeCount: 0,
};

/** Filter options are derived from the current unfiltered public feed. */
export function useTenderFacets() {
  const [facets, setFacets] = useState<Facets>(emptyFacets);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    fetchAllTenders({ filters: EMPTY_FILTERS, page: 1, pageSize: MAX_PAGE_SIZE })
      .then((page) => {
        if (!active) return;
        const derived = deriveFacets(page.items);
        setFacets({
          categories: derived.categories,
          provinces: derived.provinces,
          districts: derived.districts,
          municipalities: derived.municipalities,
          organizations: derived.organizations,
          sources: derived.sources,
          noticeCount: page.items.length,
        });
        setLoaded(true);
      })
      .catch(() => {
        if (active) setLoaded(true);
      });
    return () => {
      active = false;
    };
  }, []);

  return { ...facets, loaded };
}
