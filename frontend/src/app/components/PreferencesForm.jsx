'use client';

import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
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
  Switch,
  Text,
} from '@mantine/core';
import { RangeSlider } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconAlertCircle, IconCheck, IconX } from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';
import { parseApiErrorResponse } from '../../../lib/errorHandling';
import { GENDER_IDENTITY_OPTIONS, normalizeGenderIdentity } from '../../../lib/genderIdentity';
import { apiFetch } from '../../../lib/api';
import {
  FURNISHED_PREF_OPTIONS,
  GENDER_POLICY_OPTIONS,
  LEASE_TYPE_OPTIONS,
  PREFERENCE_PAYLOAD_KEYS,
  formatPrice,
  normalizeBathroomsPreference,
  normalizeIntInput,
  normalizeNumericInput,
  pickPreferenceFields,
  withSelectedOption,
} from '../../features/preferences/lib/index';
import { useLocationOptions } from '../../features/preferences/hooks/useLocationOptions';
import { usePriceHistogram } from '../../features/preferences/hooks/usePriceHistogram';
import { PriceHistogram } from '../../features/preferences/components/PriceHistogram';
import { RoomCounter } from '../../features/preferences/components/RoomCounter';

const PREFS_SHADOW_TTL_MS = 60 * 1000;

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

const DEFAULT_PREFS = {
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
  lifestyle_preferences: null,
};

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

  const [citySearch, setCitySearch] = useState('');
  const [allowLargerLayouts, setAllowLargerLayouts] = useState(false);
  const [genderIdentity, setGenderIdentity] = useState(null);

  const [prefs, setPrefs] = useState(DEFAULT_PREFS);
  const updatePref = useCallback((key, value) => setPrefs((prev) => ({ ...prev, [key]: value })), []);

  // ── Location options ───────────────────────────────────────────────────────

  const { countryOptions, stateOptions, cityOptions, loadingStates, loadingCities } =
    useLocationOptions({
      country: prefs.target_country,
      state: prefs.target_state_province,
      city: prefs.target_city,
      citySearch,
      onStateNormalize: useCallback((v) => updatePref('target_state_province', v), [updatePref]),
      onCityNormalize: useCallback((v) => updatePref('target_city', v), [updatePref]),
    });

  // ── Price histogram ────────────────────────────────────────────────────────

  const {
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
  } = usePriceHistogram({ city: prefs.target_city, preserveRange: true });

  // ── Shadow prefs (localStorage optimistic cache) ───────────────────────────

  // Apply shadow prefs exactly once after userId is known, before the API
  // response arrives, so the form doesn't appear blank.
  useLayoutEffect(() => {
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
      target_bathrooms: normalizeBathroomsPreference(shadowPrefs.target_bathrooms),
    }));
    setAllowLargerLayouts(Boolean(shadowPrefs?.lifestyle_preferences?.allow_larger_layouts));
    setGenderIdentity(normalizeGenderIdentity(shadowPrefs?.lifestyle_preferences?.gender_identity));
    appliedShadowRef.current = true;
  }, [userId]);

  // ── Saved preferences query ────────────────────────────────────────────────

  const { data: savedPrefs, isLoading: prefsLoading } = useQuery({
    queryKey: ['preferences', userId],
    queryFn: async () => {
      const res = await apiFetch(`/preferences/${userId}`, {}, { token: authState.accessToken });
      if (!res.ok) throw new Error('Failed to load preferences');
      return (await res.json()).data || {};
    },
    enabled: !!userId && !!authState?.accessToken,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Sync query data → form state exactly once per new result.
  useLayoutEffect(() => {
    if (!savedPrefs || savedPrefs === prevPrefsRef.current) return;

    // Don't overwrite form if the user has shadow prefs with a different location
    // (they made changes before the fetch completed).
    const shadow = readPrefsShadow(userId);
    if (shadow?.prefs) {
      const sp = shadow.prefs;
      const locationMismatch =
        (savedPrefs.target_country || null) !== (sp.target_country || null) ||
        (savedPrefs.target_state_province || null) !== (sp.target_state_province || null) ||
        (savedPrefs.target_city || null) !== (sp.target_city || null);
      if (locationMismatch) return;
    }

    prevPrefsRef.current = savedPrefs;

    setPrefs({
      target_country: savedPrefs.target_country || 'US',
      target_state_province: savedPrefs.target_state_province || null,
      target_city: savedPrefs.target_city || null,
      required_bedrooms: savedPrefs.required_bedrooms ?? null,
      target_bathrooms: normalizeBathroomsPreference(savedPrefs.target_bathrooms),
      target_deposit_amount: savedPrefs.target_deposit_amount ?? null,
      furnished_preference: savedPrefs.furnished_preference || 'no_preference',
      gender_policy: savedPrefs.gender_policy || 'mixed_ok',
      move_in_date: savedPrefs.move_in_date || null,
      target_lease_type: savedPrefs.target_lease_type || null,
      target_lease_duration_months: savedPrefs.target_lease_duration_months ?? null,
      lifestyle_preferences: savedPrefs.lifestyle_preferences || null,
    });
    setAllowLargerLayouts(Boolean(savedPrefs?.lifestyle_preferences?.allow_larger_layouts));
    setGenderIdentity(normalizeGenderIdentity(savedPrefs?.lifestyle_preferences?.gender_identity));

    if (savedPrefs.budget_min != null || savedPrefs.budget_max != null) {
      setPriceRange([savedPrefs.budget_min ?? 0, savedPrefs.budget_max ?? 5000]);
      setPriceSliderActive(true);
    }
  }, [savedPrefs, userId, setPriceRange, setPriceSliderActive]);

  const loading = prefsLoading && !savedPrefs;

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
      const normalizedGenderIdentity = normalizeGenderIdentity(genderIdentity);
      if (prefs.gender_policy === 'same_gender_only' && !normalizedGenderIdentity) {
        setError('Please select your gender when using the "Same gender only" policy.');
        return;
      }

      const lifestylePayload = {
        ...(prefs.lifestyle_preferences || {}),
        allow_larger_layouts: allowLargerLayouts,
      };
      if (normalizedGenderIdentity) {
        lifestylePayload.gender_identity = normalizedGenderIdentity;
      } else {
        delete lifestylePayload.gender_identity;
      }

      const normalizedPrefs = pickPreferenceFields(prefs);
      const payload = {
        ...normalizedPrefs,
        target_bathrooms: normalizeBathroomsPreference(normalizedPrefs.target_bathrooms),
        budget_min: priceSliderActive ? priceRange[0] : null,
        budget_max: priceSliderActive ? priceRange[1] : null,
        target_deposit_amount: normalizeNumericInput(prefs.target_deposit_amount),
        target_lease_duration_months: normalizeIntInput(prefs.target_lease_duration_months),
        target_lease_type: prefs.target_lease_type || 'any',
        lifestyle_preferences: lifestylePayload,
        move_in_date:
          prefs.move_in_date instanceof Date
            ? prefs.move_in_date.toISOString().split('T')[0]
            : prefs.move_in_date,
      };

      const response = await apiFetch(
        `/preferences/${userId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        { token: authState.accessToken }
      );

      if (!response.ok) {
        const parsedError = await parseApiErrorResponse(response, 'Failed to save preferences');
        throw new Error(parsedError.message);
      }

      const saveResult = await response.json();
      const persistedPrefs = saveResult?.data || payload;

      const prevLocation = prevPrefsRef.current || savedPrefs || {};
      const locationChanged =
        (prevLocation.target_country || null) !== (persistedPrefs.target_country || null) ||
        (prevLocation.target_state_province || null) !== (persistedPrefs.target_state_province || null) ||
        (prevLocation.target_city || null) !== (persistedPrefs.target_city || null);

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
      setGenderIdentity(
        normalizeGenderIdentity(persistedPrefs?.lifestyle_preferences?.gender_identity)
      );

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);

      queryClient.invalidateQueries({ queryKey: ['preferences', userId], refetchType: 'inactive' });
      queryClient.invalidateQueries({ queryKey: ['user-prefs', userId] });
      queryClient.invalidateQueries({ queryKey: ['discover-feed', userId], refetchType: 'all' });
      queryClient.invalidateQueries({ queryKey: ['matches-feed', userId], refetchType: 'all' });

      // Signal to the Matches page that preferences changed so it can offer a
      // "Reload Matches" button without forcing an immediate re-fetch.
      if (typeof window !== 'undefined' && userId) {
        try {
          localStorage.setItem(`padly_matches_stale_at_${userId}`, String(Date.now()));
        } catch {
          // Ignore storage errors.
        }
      }

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

  const bathroomCounterValue =
    prefs.target_bathrooms == null ? null : Math.max(1, Math.round(prefs.target_bathrooms));

  const handleBathroomChange = (counterVal) => {
    updatePref('target_bathrooms', counterVal === null ? null : counterVal);
  };

  // ── Loading ───────────────────────────────────────────────────────────────

  if (authLoading || loading) {
    return (
      <Stack
        align="center"
        gap="md"
        py="xl"
        style={{ minHeight: '300px', justifyContent: 'center' }}
      >
        <Loader size="lg" />
        <Text c="dimmed">
          {authLoading ? 'Checking authentication...' : 'Loading your preferences...'}
        </Text>
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
          rightSection={
            prefs.target_city ? (
              <ActionIcon
                variant="subtle"
                color="gray"
                radius="xl"
                size="sm"
                aria-label="Clear selected city"
                onClick={(event) => {
                  event.stopPropagation();
                  updatePref('target_city', null);
                  setCitySearch('');
                }}
              >
                <IconX size={14} />
              </ActionIcon>
            ) : null
          }
          rightSectionPointerEvents={prefs.target_city ? 'all' : 'none'}
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
          <Box
            style={{ padding: '1.5rem', background: '#f8f9fa', borderRadius: 10, textAlign: 'center' }}
          >
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
                thumb: {
                  width: 26,
                  height: 26,
                  borderWidth: 2,
                  borderColor: '#adb5bd',
                  backgroundColor: '#fff',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.18)',
                },
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
                    {priceRange[1] >= sliderMax
                      ? `${formatPrice(priceRange[1])}+`
                      : formatPrice(priceRange[1])}
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
            <RoomCounter label="Bathrooms" value={bathroomCounterValue} onChange={handleBathroomChange} />
          </Box>
        </Stack>

        <Switch
          label="Allow larger listings"
          description="Off = exact bed/bath match. On = show listings with more beds/baths than selected."
          checked={allowLargerLayouts}
          onChange={(event) => setAllowLargerLayouts(event.currentTarget.checked)}
        />

        <Select
          label="Furnished preference"
          description="'Required' hard-filters listings; 'Preferred' boosts ranking"
          data={FURNISHED_PREF_OPTIONS}
          value={prefs.furnished_preference}
          onChange={(v) => updatePref('furnished_preference', v || 'no_preference')}
        />

        <Select
          label="Lease type"
          placeholder="Any"
          data={LEASE_TYPE_OPTIONS}
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

      {/* ── TIMING & HOUSEHOLD ── */}
      <Stack gap="md">
        <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
          Timing &amp; Household
        </Text>

        <DatePickerInput
          label="Move-in date"
          description="Listings available within 60 days of this date will be prioritised"
          placeholder="Select date"
          value={prefs.move_in_date ? new Date(prefs.move_in_date) : null}
          onChange={(date) =>
            updatePref('move_in_date', date ? date.toISOString().split('T')[0] : null)
          }
          minDate={new Date()}
          clearable
        />

        <Select
          label="Your gender"
          description="Used to enforce same-gender matching when selected below."
          placeholder="Select your gender"
          data={GENDER_IDENTITY_OPTIONS}
          value={genderIdentity}
          onChange={setGenderIdentity}
          clearable
          withAsterisk={prefs.gender_policy === 'same_gender_only'}
        />

        <Select
          label="Gender policy"
          description="Used for group compatibility matching"
          data={GENDER_POLICY_OPTIONS}
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
