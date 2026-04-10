'use client';

import { useState, useEffect, useRef } from 'react';
import { apiFetch } from '../../../../lib/api';
import { withSelectedOption, findMatchingOption } from '../lib/index';

/**
 * Manages country, state, and city select options, including async loading and
 * optional value normalisation (correcting stored values to the API canonical form).
 *
 * @param {object}      params
 * @param {string|null} params.country          - Currently selected country code.
 * @param {string|null} params.state            - Currently selected state/province code.
 * @param {string|null} params.city             - Currently selected city value.
 * @param {string}      params.citySearch       - The current city search string.
 * @param {function}    [params.onStateNormalize] - Called with the canonical state value when
 *   the API returns a differently-cased/formatted match for the stored state. Optional.
 * @param {function}    [params.onCityNormalize]  - Same, for city. Optional.
 *
 * @returns {{
 *   countryOptions: array,
 *   stateOptions:   array,
 *   cityOptions:    array,
 *   loadingStates:  boolean,
 *   loadingCities:  boolean,
 * }}
 */
export function useLocationOptions({
  country,
  state,
  city,
  citySearch,
  onStateNormalize,
  onCityNormalize,
}) {
  const [countryOptions, setCountryOptions] = useState([]);
  const [stateOptions, setStateOptions] = useState([]);
  const [cityOptions, setCityOptions] = useState([]);
  const [loadingStates, setLoadingStates] = useState(false);
  const [loadingCities, setLoadingCities] = useState(false);

  // Stable refs so callbacks never need to be in effect dependency arrays.
  const onStateNormalizeRef = useRef(onStateNormalize);
  const onCityNormalizeRef = useRef(onCityNormalize);
  useEffect(() => { onStateNormalizeRef.current = onStateNormalize; });
  useEffect(() => { onCityNormalizeRef.current = onCityNormalize; });

  // Load countries once on mount.
  useEffect(() => {
    apiFetch('/options/countries')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setCountryOptions(d.data || []))
      .catch(() => {});
  }, []);

  // Load states whenever the selected country (or state) changes.
  // `state` is included so the current value is always injected into the list
  // via `withSelectedOption`, even if it arrived from saved/shadow prefs before
  // the API response returned.
  useEffect(() => {
    if (!country) {
      setStateOptions([]);
      setLoadingStates(false);
      return;
    }

    const controller = new AbortController();
    setLoadingStates(true);

    apiFetch(`/options/states?country_code=${encodeURIComponent(country)}`, {
      signal: controller.signal,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const apiOptions = d.data || [];
        setStateOptions(withSelectedOption(apiOptions, state));

        if (state && onStateNormalizeRef.current) {
          const matched = findMatchingOption(apiOptions, state);
          if (matched && matched.value !== state) {
            onStateNormalizeRef.current(matched.value);
          }
        }
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') setStateOptions([]);
      })
      .finally(() => setLoadingStates(false));

    return () => controller.abort();
  }, [country, state]);

  // Load cities whenever country, state, or citySearch changes.
  useEffect(() => {
    if (!country || !state) {
      setCityOptions([]);
      setLoadingCities(false);
      return;
    }

    const controller = new AbortController();
    setLoadingCities(true);

    apiFetch(
      `/options/cities?country_code=${encodeURIComponent(country)}&state_code=${encodeURIComponent(state)}&q=${encodeURIComponent(citySearch ?? '')}&limit=250`,
      { signal: controller.signal }
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const apiOptions = d.data || [];
        setCityOptions(withSelectedOption(apiOptions, city));

        if (city && onCityNormalizeRef.current) {
          const matched = findMatchingOption(apiOptions, city);
          if (matched && matched.value !== city) {
            onCityNormalizeRef.current(matched.value);
          }
        }
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') setCityOptions([]);
      })
      .finally(() => setLoadingCities(false));

    return () => controller.abort();
  }, [country, state, citySearch]);

  return { countryOptions, stateOptions, cityOptions, loadingStates, loadingCities };
}
