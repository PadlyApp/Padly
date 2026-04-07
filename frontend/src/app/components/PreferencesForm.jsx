'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ActionIcon,
  Alert,
  Box,
  Button,
  Divider,
  Group,
  Loader,
  NumberInput,
  Select,
  Stack,
  Text,
} from '@mantine/core';
import { RangeSlider } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconAlertCircle, IconCheck, IconMinus, IconPlus } from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';
import { parseApiErrorResponse } from '../../../lib/errorHandling';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const NUM_HISTOGRAM_BINS = 30;
const PREFS_SHADOW_TTL_MS = 60 * 1000;
const PREFERENCE_PAYLOAD_KEYS = [
  'target_country',
  'target_state_province',
  'target_city',
  'required_bedrooms',
  'target_bathrooms',
  'target_deposit_amount',
  'furnished_preference',
  'gender_policy',
  'move_in_date',
  'target_lease_type',
  'target_lease_duration_months',
];

function pickPreferenceFields(source) {
  const out = {};
  for (const key of PREFERENCE_PAYLOAD_KEYS) {
    if (Object.prototype.hasOwnProperty.call(source || {}, key)) {
      out[key] = source[key];
    }
  }
  return out;
}

function prefsShadowKey(userId) {
  return userId ? `padly:prefs-shadow:${userId}` : null;
}

function readPrefsShadow(userId) {
  const key = prefsShadowKey(userId);
  if (!key || typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.savedAt || !parsed?.prefs) return null;
    if (Date.now() - parsed.savedAt > PREFS_SHADOW_TTL_MS) {
      window.localStorage.removeItem(key);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function writePrefsShadow(userId, prefs) {
  const key = prefsShadowKey(userId);
  if (!key || typeof window === 'undefined' || !prefs) return;
  try {
    window.localStorage.setItem(key, JSON.stringify({ savedAt: Date.now(), prefs }));
  } catch {
    // Ignore storage failures silently.
  }
}

function formatPrice(val) {
  return `$${Math.round(val).toLocaleString()}`;
}

function normalizeNumericInput(value) {
  if (value === '' || value == null) return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeIntInput(value) {
  const parsed = normalizeNumericInput(value);
  if (parsed == null) return null;
  return Math.trunc(parsed);
}

function normalizeOptionText(value) {
  return String(value || '').trim().toLowerCase();
}

function findMatchingOption(options, selectedValue) {
  if (!selectedValue) return null;
  const selectedNorm = normalizeOptionText(selectedValue);
  return options.find((opt) => {
    const valueNorm = normalizeOptionText(opt?.value);
    const labelNorm = normalizeOptionText(opt?.label);
    return selectedNorm === valueNorm || selectedNorm === labelNorm;
  }) || null;
}

function withSelectedOption(options, selectedValue) {
  if (!selectedValue) return options;
  const exists = options.some((opt) => (opt?.value ?? null) === selectedValue);
  if (exists) return options;
  return [{ value: selectedValue, label: selectedValue }, ...options];
}

function RoomCounter({ label, value, onChange }) {
  const decrement = () => onChange(value === null || value <= 1 ? null : value - 1);
  const increment = () => onChange(value === null ? 1 : value + 1);

  return (
    <Group justify="space-between" align="center" py="xs">
      <Text size="sm" fw={500} style={{ minWidth: 100 }}>{label}</Text>
      <Group gap="md" align="center">
        <ActionIcon
          variant="outline"
          radius="xl"
          size="lg"
          onClick={decrement}
          disabled={value === null}
          style={{ borderColor: '#dee2e6', color: '#495057' }}
        >
          <IconMinus size={14} />
        </ActionIcon>
        <Text size="sm" fw={500} style={{ minWidth: 36, textAlign: 'center' }}>
          {value === null ? 'Any' : value}
        </Text>
        <ActionIcon
          variant="outline"
          radius="xl"
          size="lg"
          onClick={increment}
          style={{ borderColor: '#dee2e6', color: '#495057' }}
        >
          <IconPlus size={14} />
        </ActionIcon>
      </Group>
    </Group>
  );
}

function PriceHistogram({ bins, maxCount, rangeValue }) {
  if (!bins || bins.length === 0) return null;
  const [lo, hi] = rangeValue;
  return (
    <Box style={{ display: 'flex', alignItems: 'flex-end', height: 80, gap: 2, marginBottom: -1 }}>
      {bins.map((bin, i) => {
        const heightPct = maxCount > 0 ? Math.max((bin.count / maxCount) * 100, 2) : 2;
        const binMid = (bin.range_min + bin.range_max) / 2;
        const active = binMid >= lo && binMid <= hi;
        return (
          <Box
            key={i}
            style={{
              flex: 1,
              height: `${heightPct}%`,
              backgroundColor: active ? '#20c997' : '#d0d5da',
              borderRadius: '2px 2px 0 0',
              transition: 'background-color 0.08s ease, height 0.2s ease',
            }}
          />
        );
      })}
    </Box>
  );
}

export function PreferencesForm() {
  const { user, authState, isLoading: authLoading } = useAuth();
  const { tourPhase } = usePadlyTour();
  const userId = user?.profile?.id;
  const queryClient = useQueryClient();
  const prevPrefsRef = useRef(null);
  const appliedShadowRef = useRef(false);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Location options
  const [countryOptions, setCountryOptions] = useState([]);
  const [stateOptions, setStateOptions] = useState([]);
  const [cityOptions, setCityOptions] = useState([]);
  const [citySearch, setCitySearch] = useState('');
  const [loadingStates, setLoadingStates] = useState(false);
  const [loadingCities, setLoadingCities] = useState(false);

  // Price histogram state
  const [histogram, setHistogram] = useState({ bins: [], global_min: 0, global_max: 0 });
  const [priceRange, setPriceRange] = useState([0, 0]);
  const [priceSliderActive, setPriceSliderActive] = useState(false);
  const [loadingPrices, setLoadingPrices] = useState(false);

  const [prefs, setPrefs] = useState({
    target_country: 'US',
    target_state_province: null,
    target_city: null,
    required_bedrooms: null,
    target_bathrooms: null,
    target_deposit_amount: null,
    furnished_preference: 'no_preference',
    gender_policy: 'mixed_ok',
    move_in_date: null,
    target_lease_type: null,
    target_lease_duration_months: null,
  });

  const updatePref = (key, value) => setPrefs((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    if (!userId || appliedShadowRef.current) return;
    const shadow = readPrefsShadow(userId);
    if (!shadow?.prefs) return;
    const shadowPrefs = pickPreferenceFields(shadow.prefs);
    setPrefs((prev) => ({
      ...prev,
      ...shadowPrefs,
      target_country: shadowPrefs.target_country || prev.target_country,
      target_state_province: shadowPrefs.target_state_province || null,
      target_city: shadowPrefs.target_city || null,
    }));
    setStateOptions((prev) => withSelectedOption(prev, shadowPrefs.target_state_province));
    if (shadowPrefs.target_city) {
      setCityOptions((prev) => withSelectedOption(prev, shadowPrefs.target_city));
    }
    appliedShadowRef.current = true;
  }, [userId]);

  // ── Cached preferences fetch ──────────────────────────────────────────────

  const { data: savedPrefs, isLoading: prefsLoading } = useQuery({
    queryKey: ['preferences', userId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/preferences/${userId}`, {
        headers: { Authorization: `Bearer ${authState.accessToken}`, 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error('Failed to load preferences');
      return (await res.json()).data || {};
    },
    enabled: !!userId && !!authState?.accessToken,
    staleTime: 5 * 60 * 1000,
    gcTime:    10 * 60 * 1000,
  });

  // Sync query data → controlled form state exactly once per new result
  useLayoutEffect(() => {
    if (!savedPrefs || savedPrefs === prevPrefsRef.current) return;

    const shadow = readPrefsShadow(userId);
    if (shadow?.prefs) {
      const shadowPrefs = shadow.prefs;
      const locationMismatch =
        (savedPrefs.target_country || null) !== (shadowPrefs.target_country || null) ||
        (savedPrefs.target_state_province || null) !== (shadowPrefs.target_state_province || null) ||
        (savedPrefs.target_city || null) !== (shadowPrefs.target_city || null);
      if (locationMismatch) {
        return;
      }
    }

    prevPrefsRef.current = savedPrefs;

    if (savedPrefs.target_state_province) {
      setStateOptions((prev) => withSelectedOption(prev, savedPrefs.target_state_province));
    }

    if (savedPrefs.target_city) {
      setCityOptions([{ value: savedPrefs.target_city, label: savedPrefs.target_city }]);
    }

    setPrefs({
      target_country: savedPrefs.target_country || 'US',
      target_state_province: savedPrefs.target_state_province || null,
      target_city: savedPrefs.target_city || null,
      required_bedrooms: savedPrefs.required_bedrooms ?? null,
      target_bathrooms: savedPrefs.target_bathrooms ?? null,
      target_deposit_amount: savedPrefs.target_deposit_amount ?? null,
      furnished_preference: savedPrefs.furnished_preference || 'no_preference',
      gender_policy: savedPrefs.gender_policy || 'mixed_ok',
      move_in_date: savedPrefs.move_in_date || null,
      target_lease_type: savedPrefs.target_lease_type || null,
      target_lease_duration_months: savedPrefs.target_lease_duration_months ?? null,
    });

    if (savedPrefs.budget_min != null || savedPrefs.budget_max != null) {
      setPriceRange([savedPrefs.budget_min ?? 0, savedPrefs.budget_max ?? 5000]);
      setPriceSliderActive(true);
    }
  }, [savedPrefs, userId]);

  // Only show the loading skeleton on the very first fetch (no cached data yet)
  const loading = prefsLoading && !savedPrefs;

  // ── Effects ──────────────────────────────────────────────────────────────

  useEffect(() => {
    fetch(`${API_BASE}/api/options/countries`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setCountryOptions(d.data || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const country = prefs.target_country;
    if (!country) {
      setStateOptions([]);
      setLoadingStates(false);
      return;
    }

    const controller = new AbortController();
    setLoadingStates(true);

    fetch(`${API_BASE}/api/options/states?country_code=${encodeURIComponent(country)}`, { signal: controller.signal })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (!d) return;
        const apiOptions = d.data || [];
        const current = prefs.target_state_province;
        setStateOptions(withSelectedOption(apiOptions, current));

        if (!current) return;
        const matched = findMatchingOption(apiOptions, current);
        if (matched && matched.value !== current) {
          updatePref('target_state_province', matched.value);
        }
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') {
          setStateOptions([]);
        }
      })
      .finally(() => setLoadingStates(false));

    return () => controller.abort();
  }, [prefs.target_country, prefs.target_state_province]);

  useEffect(() => {
    const { target_country, target_state_province } = prefs;
    if (!target_country || !target_state_province) {
      setCityOptions([]);
      setLoadingCities(false);
      return;
    }

    const controller = new AbortController();
    setLoadingCities(true);

    fetch(
      `${API_BASE}/api/options/cities?country_code=${encodeURIComponent(target_country)}&state_code=${encodeURIComponent(target_state_province)}&q=${encodeURIComponent(citySearch)}&limit=250`,
      { signal: controller.signal }
    )
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (!d) return;
        const apiOptions = d.data || [];
        const currentCity = prefs.target_city;
        setCityOptions(withSelectedOption(apiOptions, currentCity));

        if (!currentCity) return;
        const matched = findMatchingOption(apiOptions, currentCity);
        if (matched && matched.value !== currentCity) {
          updatePref('target_city', matched.value);
        }
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') {
          setCityOptions([]);
        }
      })
      .finally(() => setLoadingCities(false));

    return () => controller.abort();
  }, [prefs.target_country, prefs.target_state_province, citySearch]);

  // Fetch price histogram whenever city changes
  useEffect(() => {
    const city = prefs.target_city;
    if (!city) {
      setHistogram({ bins: [], global_min: 0, global_max: 0 });
      setPriceSliderActive(false);
      return;
    }
    setLoadingPrices(true);
    fetch(
      `${API_BASE}/api/listings/price-histogram?city=${encodeURIComponent(city)}&status=active&bins=${NUM_HISTOGRAM_BINS}`
    )
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        const data = d?.data;
        if (data && data.total_count > 0) {
          const effectiveMax = data.display_max ?? data.global_max;
          setHistogram({ bins: data.bins, global_min: data.global_min, global_max: effectiveMax });
          // Only reset slider to full range if not already set from saved prefs
          setPriceRange((prev) => {
            const alreadySet = prev[0] !== 0 || prev[1] !== 0;
            if (alreadySet) return prev;
            return [data.global_min, effectiveMax];
          });
        } else {
          setHistogram({ bins: [], global_min: 500, global_max: 5000 });
          setPriceRange((prev) => (prev[0] !== 0 || prev[1] !== 0) ? prev : [500, 5000]);
        }
        setPriceSliderActive(true);
      })
      .catch(() => {
        setHistogram({ bins: [], global_min: 500, global_max: 5000 });
        setPriceRange((prev) => (prev[0] !== 0 || prev[1] !== 0) ? prev : [500, 5000]);
        setPriceSliderActive(true);
      })
      .finally(() => setLoadingPrices(false));
  }, [prefs.target_city]);

  // ── Save ─────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!userId || !authState?.accessToken) {
      setError('You must be logged in to save preferences.');
      return;
    }
    if (!prefs.target_country || !prefs.target_state_province || !prefs.target_city) {
      setError('Please choose country, state/province, and city.');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      const normalizedPrefs = pickPreferenceFields(prefs);
      const payload = {
        ...normalizedPrefs,
        budget_min: priceSliderActive ? priceRange[0] : null,
        budget_max: priceSliderActive ? priceRange[1] : null,
        target_deposit_amount: normalizeNumericInput(prefs.target_deposit_amount),
        target_lease_duration_months: normalizeIntInput(prefs.target_lease_duration_months),
        target_lease_type: prefs.target_lease_type || 'any',
        move_in_date: prefs.move_in_date instanceof Date
          ? prefs.move_in_date.toISOString().split('T')[0]
          : prefs.move_in_date,
      };

      const response = await fetch(`${API_BASE}/api/preferences/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authState.accessToken}` },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const parsedError = await parseApiErrorResponse(response, 'Failed to save preferences');
        throw new Error(parsedError.message);
      }

      const saveResult = await response.json();
      const persistedPrefs = saveResult?.data || payload;
      const previousPersistedPrefs = prevPrefsRef.current || savedPrefs || {};
      const previousLocation = {
        target_country: previousPersistedPrefs.target_country || null,
        target_state_province: previousPersistedPrefs.target_state_province || null,
        target_city: previousPersistedPrefs.target_city || null,
      };
      const nextLocation = {
        target_country: persistedPrefs.target_country || null,
        target_state_province: persistedPrefs.target_state_province || null,
        target_city: persistedPrefs.target_city || null,
      };
      const locationChanged =
        previousLocation.target_country !== nextLocation.target_country ||
        previousLocation.target_state_province !== nextLocation.target_state_province ||
        previousLocation.target_city !== nextLocation.target_city;

      queryClient.setQueryData(['preferences', userId], persistedPrefs);
      queryClient.setQueryData(['user-prefs', userId], persistedPrefs);
      writePrefsShadow(userId, persistedPrefs);
      prevPrefsRef.current = persistedPrefs;
      setPrefs((prev) => ({
        ...prev,
        target_country: persistedPrefs.target_country || prev.target_country,
        target_state_province: persistedPrefs.target_state_province || null,
        target_city: persistedPrefs.target_city || null,
      }));
      setStateOptions((prev) => withSelectedOption(prev, persistedPrefs.target_state_province));
      if (persistedPrefs.target_city) {
        setCityOptions((prev) => withSelectedOption(prev, persistedPrefs.target_city));
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
      queryClient.invalidateQueries({ queryKey: ['preferences', userId], refetchType: 'inactive' });
      queryClient.invalidateQueries({ queryKey: ['user-prefs', userId] });
      queryClient.invalidateQueries({ queryKey: ['discover-feed', userId], refetchType: 'all' });
      queryClient.invalidateQueries({ queryKey: ['matches-feed', userId], refetchType: 'all' });

      if (locationChanged && typeof window !== 'undefined') {
        try {
          sessionStorage.removeItem(`padly_discover_progress:${userId}`);
        } catch {
          // Ignore storage failures silently.
        }
      }

      window.scrollTo({ top: 0, behavior: 'smooth' });

      if (tourPhase === 'preferences') {
        window.dispatchEvent(new CustomEvent('padly-tour-prefs-saved'));
      }
    } catch (err) {
      setError(err.message || 'Network error. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // ── Derived values ────────────────────────────────────────────────────────

  const sliderMin = histogram.global_min || 0;
  const sliderMax = histogram.global_max || 5000;

  const maxBinCount = histogram.bins.length > 0
    ? Math.max(...histogram.bins.map((b) => b.count))
    : 0;

  const listingsInRange = useMemo(() => {
    if (!histogram.bins.length) return 0;
    const [lo, hi] = priceRange;
    return histogram.bins.reduce((sum, bin) => {
      if (bin.range_max <= lo || bin.range_min >= hi) return sum;
      if (bin.range_min >= lo && bin.range_max <= hi) return sum + bin.count;
      const overlap = Math.min(bin.range_max, hi) - Math.max(bin.range_min, lo);
      const width = bin.range_max - bin.range_min;
      return sum + Math.round(bin.count * (overlap / width));
    }, 0);
  }, [histogram.bins, priceRange]);

  // Bathroom counter: null=Any, 1=0.5 (share), 2+=own
  const bathroomCounterValue = prefs.target_bathrooms == null
    ? null
    : prefs.target_bathrooms < 1 ? 1 : Math.round(prefs.target_bathrooms);

  const handleBathroomChange = (counterVal) => {
    if (counterVal === null) { updatePref('target_bathrooms', null); return; }
    updatePref('target_bathrooms', counterVal === 1 ? 0.5 : counterVal);
  };

  // ── Loading ───────────────────────────────────────────────────────────────

  if (authLoading || loading) {
    return (
      <Stack align="center" gap="md" py="xl" style={{ minHeight: '300px', justifyContent: 'center' }}>
        <Loader size="lg" />
        <Text c="dimmed">{authLoading ? 'Checking authentication...' : 'Loading your preferences...'}</Text>
      </Stack>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Stack gap="xl" pb={100}>
      {success && (
        <Alert icon={<IconCheck size={16} />} title="Saved" color="green">
          Preferences updated successfully.
        </Alert>
      )}
      {error && (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )}

      {/* ── LOCATION ── */}
      <Stack gap="md" data-tour="prefs-hard">
        <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
          Location
        </Text>

        <Select
          label="Country"
          placeholder="Select country"
          data={countryOptions}
          value={prefs.target_country}
          onChange={(v) => {
            updatePref('target_country', v);
            updatePref('target_state_province', null);
            updatePref('target_city', null);
            setStateOptions([]);
            setCityOptions([]);
            setCitySearch('');
          }}
          required
        />

        <Select
          label="State / Province"
          placeholder="Select state/province"
          data={stateOptions}
          value={prefs.target_state_province}
          onChange={(v) => {
            updatePref('target_state_province', v);
            updatePref('target_city', null);
            setCityOptions([]);
            setCitySearch('');
          }}
          searchable
          disabled={!prefs.target_country || loadingStates}
          required
        />

        <Select
          label="City"
          description="Choose a city or metro (e.g. New York, NYC, Bay Area, GTA)."
          placeholder={prefs.target_state_province ? 'Search city' : 'Select state/province first'}
          data={cityOptions}
          value={prefs.target_city}
          onChange={(v) => updatePref('target_city', v)}
          searchable
          searchValue={citySearch}
          onSearchChange={setCitySearch}
          disabled={!prefs.target_state_province || loadingCities}
          required
        />
      </Stack>

      <Divider />

      {/* ── BUDGET ── */}
      <Stack gap="sm">
        <Group justify="space-between" align="center">
          <Stack gap={2}>
            <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
              Budget
            </Text>
            <Text size="xs" c="dimmed">Monthly rent, includes all fees</Text>
          </Stack>
          {loadingPrices && <Text size="xs" c="dimmed">Loading…</Text>}
        </Group>

        {!prefs.target_city && (
          <Box style={{ padding: '1.5rem', background: '#f8f9fa', borderRadius: 10, textAlign: 'center' }}>
            <Text size="sm" c="dimmed">Select a city above to see prices in that area</Text>
          </Box>
        )}

        {prefs.target_city && priceSliderActive && (
          <Box>
            <PriceHistogram bins={histogram.bins} maxCount={maxBinCount} rangeValue={priceRange} />
            <RangeSlider
              min={sliderMin}
              max={sliderMax}
              step={Math.max(1, Math.round((sliderMax - sliderMin) / 300))}
              value={priceRange}
              onChange={setPriceRange}
              color="teal"
              label={null}
              thumbSize={26}
              styles={{
                root: { marginTop: 0 },
                track: { height: 3, backgroundColor: '#d0d5da' },
                bar: { backgroundColor: '#20c997' },
                thumb: { width: 26, height: 26, borderWidth: 2, borderColor: '#adb5bd', backgroundColor: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.18)' },
              }}
            />
            <Group justify="space-between" mt={12}>
              <Stack gap={3} align="flex-start">
                <Text size="xs" c="dimmed" fw={500}>Minimum</Text>
                <Box style={{ border: '1.5px solid #dee2e6', borderRadius: 24, padding: '5px 16px', background: '#fff' }}>
                  <Text size="sm" fw={600}>{formatPrice(priceRange[0])}</Text>
                </Box>
              </Stack>
              <Stack gap={3} align="center">
                <Text size="xs" c="dimmed" fw={500}>&nbsp;</Text>
                <Text size="xs" c="dimmed" fw={500} style={{ whiteSpace: 'nowrap' }}>
                  {listingsInRange.toLocaleString()} listing{listingsInRange !== 1 ? 's' : ''}
                </Text>
              </Stack>
              <Stack gap={3} align="flex-end">
                <Text size="xs" c="dimmed" fw={500}>Maximum</Text>
                <Box style={{ border: '1.5px solid #dee2e6', borderRadius: 24, padding: '5px 16px', background: '#fff' }}>
                  <Text size="sm" fw={600}>
                    {priceRange[1] >= sliderMax ? `${formatPrice(priceRange[1])}+` : formatPrice(priceRange[1])}
                  </Text>
                </Box>
              </Stack>
            </Group>
          </Box>
        )}

        <NumberInput
          label="Max deposit"
          description="Optional. Leave blank to skip."
          placeholder="Highest deposit you can pay"
          value={prefs.target_deposit_amount ?? ''}
          onChange={(v) => updatePref('target_deposit_amount', normalizeNumericInput(v))}
          min={0}
          prefix="$"
          mt="xs"
        />
      </Stack>

      <Divider />

      {/* ── HOUSING ── */}
      <Stack gap="md">
        <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
          Housing
        </Text>

        <Stack gap={0} style={{ border: '1px solid #e9ecef', borderRadius: 10, overflow: 'hidden' }}>
          <Box style={{ padding: '0 16px' }}>
            <RoomCounter
              label="Bedrooms"
              value={prefs.required_bedrooms}
              onChange={(v) => updatePref('required_bedrooms', v)}
            />
          </Box>
          <Divider />
          <Box style={{ padding: '0 16px' }}>
            <RoomCounter
              label="Bathrooms"
              value={bathroomCounterValue}
              onChange={handleBathroomChange}
            />
          </Box>
        </Stack>

        <Select
          label="Furnished preference"
          description="'Required' hard-filters listings; 'Preferred' boosts ranking"
          data={[
            { value: 'required', label: 'Must be furnished' },
            { value: 'preferred', label: 'Prefer furnished' },
            { value: 'no_preference', label: 'No preference' },
          ]}
          value={prefs.furnished_preference}
          onChange={(v) => updatePref('furnished_preference', v || 'no_preference')}
        />

        <Select
          label="Lease type"
          placeholder="Any"
          data={[
            { value: 'fixed', label: 'Fixed-term lease' },
            { value: 'month_to_month', label: 'Month-to-month' },
            { value: 'sublet', label: 'Sublet' },
            { value: 'any', label: 'Any' },
          ]}
          value={prefs.target_lease_type}
          onChange={(v) => updatePref('target_lease_type', v)}
          clearable
        />

        <NumberInput
          label="Lease duration (months)"
          placeholder="e.g. 12"
          value={prefs.target_lease_duration_months ?? ''}
          onChange={(v) => updatePref('target_lease_duration_months', normalizeIntInput(v))}
          min={1}
          max={24}
        />
      </Stack>

      <Divider />

      {/* ── TIMING ── */}
      <Stack gap="md">
        <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
          Timing &amp; Household
        </Text>

        <DatePickerInput
          label="Move-in date"
          description="Listings available within 60 days of this date will be prioritised"
          placeholder="Select date"
          value={prefs.move_in_date ? new Date(prefs.move_in_date) : null}
          onChange={(date) => updatePref('move_in_date', date ? date.toISOString().split('T')[0] : null)}
          minDate={new Date()}
          clearable
        />

        <Select
          label="Gender policy"
          description="Used for group compatibility matching"
          data={[
            { value: 'mixed_ok', label: 'Mixed gender is okay' },
            { value: 'same_gender_only', label: 'Same gender only' },
          ]}
          value={prefs.gender_policy}
          onChange={(v) => updatePref('gender_policy', v || 'mixed_ok')}
        />
      </Stack>

      {/* ── Sticky save bar ── */}
      <Box
        data-tour="prefs-save"
        style={{
          position: 'sticky',
          bottom: 0,
          backgroundColor: 'white',
          padding: '1.25rem 0',
          borderTop: '1px solid #f1f1f1',
          marginTop: '1rem',
        }}
      >
        <Button size="lg" color="teal" fullWidth onClick={handleSave} loading={saving} disabled={saving}>
          Save Preferences
        </Button>
      </Box>
    </Stack>
  );
}
