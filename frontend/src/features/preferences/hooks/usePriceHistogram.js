'use client';

import { useState, useEffect, useMemo } from 'react';
import { apiFetch } from '../../../../lib/api';
import { NUM_HISTOGRAM_BINS, calcListingsInRange } from '../lib/index';

const FALLBACK_MIN = 500;
const FALLBACK_MAX = 5000;

/**
 * Fetches and manages the price histogram for a given city.
 *
 * @param {object}      options
 * @param {string|null} options.city           - The target city to fetch prices for.
 * @param {boolean}     [options.preserveRange=false] - When true, skips resetting the
 *   price range if one is already set (non-zero). Use this on the edit-preferences form
 *   so previously-saved budget bounds survive a city re-fetch.
 *
 * @returns {{
 *   histogram:        { bins: array, global_min: number, global_max: number },
 *   priceRange:       [number, number],
 *   setPriceRange:    function,
 *   priceSliderActive: boolean,
 *   setPriceSliderActive: function,
 *   loadingPrices:    boolean,
 *   sliderMin:        number,
 *   sliderMax:        number,
 *   maxBinCount:      number,
 *   listingsInRange:  number,
 * }}
 */
export function usePriceHistogram({ city, preserveRange = false }) {
  const [histogram, setHistogram] = useState({ bins: [], global_min: 0, global_max: 0 });
  const [priceRange, setPriceRange] = useState([0, 0]);
  const [priceSliderActive, setPriceSliderActive] = useState(false);
  const [loadingPrices, setLoadingPrices] = useState(false);

  useEffect(() => {
    if (!city) {
      setHistogram({ bins: [], global_min: 0, global_max: 0 });
      setPriceSliderActive(false);
      return;
    }

    setLoadingPrices(true);

    const applyRange = (min, max) => {
      setPriceRange((prev) => {
        if (preserveRange && (prev[0] !== 0 || prev[1] !== 0)) return prev;
        return [min, max];
      });
    };

    apiFetch(
      `/listings/price-histogram?city=${encodeURIComponent(city)}&status=active&bins=${NUM_HISTOGRAM_BINS}`
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const data = d?.data;
        if (data && data.total_count > 0) {
          const effectiveMax = data.display_max ?? data.global_max;
          setHistogram({ bins: data.bins, global_min: data.global_min, global_max: effectiveMax });
          applyRange(data.global_min, effectiveMax);
        } else {
          setHistogram({ bins: [], global_min: FALLBACK_MIN, global_max: FALLBACK_MAX });
          applyRange(FALLBACK_MIN, FALLBACK_MAX);
        }
        setPriceSliderActive(true);
      })
      .catch(() => {
        setHistogram({ bins: [], global_min: FALLBACK_MIN, global_max: FALLBACK_MAX });
        applyRange(FALLBACK_MIN, FALLBACK_MAX);
        setPriceSliderActive(true);
      })
      .finally(() => setLoadingPrices(false));
  }, [city, preserveRange]);

  const sliderMin = histogram.global_min || 0;
  const sliderMax = histogram.global_max || 5000;

  const maxBinCount =
    histogram.bins.length > 0 ? Math.max(...histogram.bins.map((b) => b.count)) : 0;

  const listingsInRange = useMemo(
    () => calcListingsInRange(histogram.bins, priceRange),
    [histogram.bins, priceRange]
  );

  return {
    histogram,
    priceRange,
    setPriceRange,
    priceSliderActive,
    setPriceSliderActive,
    loadingPrices,
    sliderMin,
    sliderMax,
    maxBinCount,
    listingsInRange,
  };
}
