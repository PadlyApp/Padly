'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Button,
  Collapse,
  Divider,
  Group,
  NumberInput,
  Select,
  Stack,
  Switch,
  Text,
  Title,
  Alert,
} from '@mantine/core';
import { RangeSlider } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { notifications } from '@mantine/notifications';
import {
  IconHome,
  IconCheck,
  IconAlertCircle,
  IconChevronDown,
  IconChevronUp,
} from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';
import { GENDER_IDENTITY_OPTIONS, normalizeGenderIdentity } from '../../../lib/genderIdentity';
import { apiFetch } from '../../../lib/api';
import {
  FURNISHED_PREF_OPTIONS,
  GENDER_POLICY_OPTIONS,
  LEASE_TYPE_OPTIONS,
  formatPrice,
} from '../../features/preferences/lib/index';
import { useLocationOptions } from '../../features/preferences/hooks/useLocationOptions';
import { usePriceHistogram } from '../../features/preferences/hooks/usePriceHistogram';
import { PriceHistogram } from '../../features/preferences/components/PriceHistogram';
import { RoomCounter } from '../../features/preferences/components/RoomCounter';

export default function PreferencesSetupPage() {
  const { authState, isLoading: authLoading, getValidToken } = useAuth();
  const router = useRouter();

  const isGuest = !authLoading && !authState?.accessToken;

  // ── Location state ────────────────────────────────────────────────────────

  const [stateSearch, setStateSearch] = useState('');
  const [citySearch, setCitySearch] = useState('');
  const [targetCountry, setTargetCountry] = useState(null);
  const [targetState, setTargetState] = useState(null);
  const [targetCity, setTargetCity] = useState(null);
  const [locationError, setLocationError] = useState(null);

  // ── Room / lifestyle state ────────────────────────────────────────────────

  const [bedrooms, setBedrooms] = useState(null);
  const [bathrooms, setBathrooms] = useState(null);
  const [allowLargerLayouts, setAllowLargerLayouts] = useState(false);

  // ── More filters state ────────────────────────────────────────────────────

  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [moveInDate, setMoveInDate] = useState(null);
  const [leaseType, setLeaseType] = useState(null);
  const [leaseDuration, setLeaseDuration] = useState(null);
  const [depositAmount, setDepositAmount] = useState(null);
  const [furnishedPref, setFurnishedPref] = useState('no_preference');
  const [genderPolicy, setGenderPolicy] = useState('mixed_ok');
  const [genderIdentity, setGenderIdentity] = useState(null);

  const [saving, setSaving] = useState(false);

  // ── Pre-populate from a prior guest session ───────────────────────────────

  useEffect(() => {
    if (authLoading) return;
    try {
      const raw = sessionStorage.getItem('guest_preferences');
      if (!raw) return;
      const gp = JSON.parse(raw);
      if (gp.target_country) setTargetCountry(gp.target_country);
      if (gp.target_state_province) setTargetState(gp.target_state_province);
      if (gp.target_city) setTargetCity(gp.target_city);
      if (gp.required_bedrooms != null) setBedrooms(gp.required_bedrooms);
      if (gp.target_bathrooms != null) setBathrooms(gp.target_bathrooms);
    } catch { /* best-effort */ }
  }, [authLoading]);

  // ── Location options ──────────────────────────────────────────────────────

  const { countryOptions, stateOptions, cityOptions, loadingStates, loadingCities } =
    useLocationOptions({
      country: targetCountry,
      state: targetState,
      city: targetCity,
      citySearch,
    });

  // ── Price histogram ───────────────────────────────────────────────────────

  const {
    histogram,
    priceRange,
    setPriceRange,
    priceSliderActive,
    loadingPrices,
    sliderMin,
    sliderMax,
    maxBinCount,
    listingsInRange,
  } = usePriceHistogram({ city: targetCity });

  // Restore budget range from a prior guest session after the histogram loads.
  useEffect(() => {
    if (authLoading || !priceSliderActive) return;
    try {
      const raw = sessionStorage.getItem('guest_preferences');
      if (!raw) return;
      const gp = JSON.parse(raw);
      if (gp.budget_min != null && gp.budget_max != null) {
        setPriceRange([gp.budget_min, gp.budget_max]);
      }
    } catch { /* best-effort */ }
  }, [authLoading, priceSliderActive, setPriceRange]);

  // ── Save ─────────────────────────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    const normalizedGenderIdentity = normalizeGenderIdentity(genderIdentity);
    if (!normalizedGenderIdentity) {
      notifications.show({
        title: 'Tell us your gender',
        message: 'Please select your gender so we can apply gender policy matching correctly.',
        color: 'red',
      });
      return;
    }

    if (!targetCountry || !targetState || !targetCity) {
      setLocationError('Please select a country, state/province, and city to continue.');
      return;
    }
    setLocationError(null);
    setSaving(true);

    if (isGuest) {
      const guestPrefs = {
        target_country: targetCountry,
        target_state_province: targetState,
        target_city: targetCity,
        ...(priceSliderActive ? { budget_min: priceRange[0], budget_max: priceRange[1] } : {}),
        ...(bedrooms !== null ? { required_bedrooms: bedrooms } : {}),
        ...(bathrooms !== null ? { target_bathrooms: bathrooms } : {}),
      };
      sessionStorage.setItem('guest_preferences', JSON.stringify(guestPrefs));
      router.push('/discover');
      setSaving(false);
      return;
    }

    try {
      const token = await getValidToken();
      if (!token) throw new Error('Not authenticated');

      const meRes = await apiFetch(`/auth/me`, {}, { token });
      const meData = await meRes.json();
      if (!meRes.ok) throw new Error(meData.detail || 'Failed to get user info');
      const userId = meData.user?.profile?.id;
      if (!userId) throw new Error('User profile not found');

      const body = {
        target_country: targetCountry,
        target_state_province: targetState,
        target_city: targetCity,
      };

      if (priceSliderActive) {
        body.budget_min = priceRange[0];
        body.budget_max = priceRange[1];
      }
      if (bedrooms !== null) body.required_bedrooms = bedrooms;
      if (bathrooms !== null) body.target_bathrooms = bathrooms;
      body.lifestyle_preferences = {
        allow_larger_layouts: allowLargerLayouts,
        gender_identity: normalizedGenderIdentity,
      };
      if (moveInDate) {
        body.move_in_date =
          moveInDate instanceof Date ? moveInDate.toISOString().split('T')[0] : moveInDate;
      }
      if (leaseType) body.target_lease_type = leaseType;
      if (leaseDuration) body.target_lease_duration_months = leaseDuration;
      if (depositAmount) body.target_deposit_amount = depositAmount;
      body.furnished_preference = furnishedPref;
      body.gender_policy = genderPolicy;

      const res = await apiFetch(
        `/preferences/${userId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
        { token }
      );

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to save preferences');

      notifications.show({
        title: "You're all set!",
        message: 'Your preferences have been saved.',
        color: 'teal',
        icon: <IconCheck />,
      });

      localStorage.setItem('padly_preferences_complete', 'true');
      localStorage.setItem('padly_onboarding_complete', 'true');
      router.push('/discover');
    } catch (err) {
      notifications.show({
        title: 'Could not save preferences',
        message: err.message || 'Please try again.',
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  }, [
    targetCountry, targetState, targetCity,
    priceSliderActive, priceRange,
    bedrooms, bathrooms, allowLargerLayouts,
    moveInDate, leaseType, leaseDuration, depositAmount,
    furnishedPref, genderPolicy, genderIdentity,
    getValidToken, router, isGuest,
  ]);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column' }}>
      {/* Logo header */}
      <Box style={{ borderBottom: '1px solid #e9ecef', padding: '1rem 2rem', flexShrink: 0 }}>
        <Group gap="xs" align="center">
          <Box
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: '#20c997',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <IconHome size={16} color="white" />
          </Box>
          <Text size="lg" fw={700} style={{ color: '#212529' }}>Padly</Text>
        </Group>
      </Box>

      {/* Scrollable content */}
      <Box
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          justifyContent: 'center',
          padding: '2.5rem 1.5rem 4rem',
        }}
      >
        <Stack gap="xl" style={{ width: '100%', maxWidth: 560 }}>
          {/* Header */}
          <Stack gap={4}>
            <Title order={2} fw={800} style={{ color: '#212529', lineHeight: 1.2 }}>
              Set your housing preferences
            </Title>
            <Text size="sm" c="dimmed">
              Help us find listings that match what you're looking for. You can update these anytime.
            </Text>
          </Stack>

          {isGuest && (
            <Alert color="teal" variant="light" radius="md" icon={<IconHome size={16} />}>
              You're browsing as a guest. Your preferences will be saved for this session only.{' '}
              <a href="/signup" style={{ color: '#0ca678', fontWeight: 600 }}>Create a free account</a>{' '}
              to save them permanently.
            </Alert>
          )}

          {/* ── Location ── */}
          <Stack gap="md">
            <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
              Location
            </Text>

            {locationError && (
              <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />} radius="md">
                {locationError}
              </Alert>
            )}

            <Select
              label="Country"
              placeholder="Select country"
              data={countryOptions}
              value={targetCountry}
              onChange={(val) => {
                setTargetCountry(val);
                setTargetState(null);
                setTargetCity(null);
                setStateSearch('');
                setCitySearch('');
                setLocationError(null);
              }}
            />

            <Select
              label="State / Province"
              placeholder={targetCountry ? 'Search state or province' : 'Select a country first'}
              data={stateOptions}
              value={targetState}
              onChange={(val) => {
                setTargetState(val);
                setTargetCity(null);
                setCitySearch('');
                setLocationError(null);
              }}
              searchable
              searchValue={stateSearch}
              onSearchChange={setStateSearch}
              disabled={!targetCountry || loadingStates}
              nothingFoundMessage={stateOptions.length === 0 ? 'Loading…' : 'No results'}
            />

            <Select
              label="City"
              placeholder={targetState ? 'Search for a city' : 'Select a state first'}
              data={cityOptions}
              value={targetCity}
              onChange={(val) => { setTargetCity(val); setLocationError(null); }}
              onSearchChange={setCitySearch}
              searchValue={citySearch}
              disabled={!targetState || loadingCities}
              searchable
              nothingFoundMessage={targetState ? 'No cities found' : 'Select a state first'}
            />
          </Stack>

          <Divider />

          {/* ── Price range ── */}
          <Stack gap="sm">
            <Group justify="space-between" align="center">
              <Stack gap={2}>
                <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
                  Price range
                </Text>
                <Text size="xs" c="dimmed">Monthly rent, includes all fees</Text>
              </Stack>
              {loadingPrices && <Text size="xs" c="dimmed">Loading…</Text>}
            </Group>

            {!targetCity && (
              <Box
                style={{
                  padding: '1.5rem',
                  background: '#f8f9fa',
                  borderRadius: 10,
                  textAlign: 'center',
                }}
              >
                <Text size="sm" c="dimmed">Select a city above to see prices in that area</Text>
              </Box>
            )}

            {targetCity && priceSliderActive && (
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
          </Stack>

          <Divider />

          {/* ── Rooms and beds ── */}
          <Stack gap="md">
            <Text size="sm" fw={700} tt="uppercase" style={{ color: '#868e96', letterSpacing: '0.06em' }}>
              Rooms and beds
            </Text>

            <Stack gap={0} style={{ border: '1px solid #e9ecef', borderRadius: 10, overflow: 'hidden' }}>
              <Box style={{ padding: '0 16px' }}>
                <RoomCounter label="Bedrooms" value={bedrooms} onChange={setBedrooms} />
              </Box>
              <Divider />
              <Box style={{ padding: '0 16px' }}>
                <RoomCounter label="Bathrooms" value={bathrooms} onChange={setBathrooms} />
              </Box>
            </Stack>

            <Switch
              label="Allow larger listings"
              description="Off = exact bed/bath match. On = show listings with more beds/baths than selected."
              checked={allowLargerLayouts}
              onChange={(event) => setAllowLargerLayouts(event.currentTarget.checked)}
            />

            <Select
              label="Your gender"
              placeholder="Select your gender"
              description="Used for roommate compatibility when gender preferences apply."
              data={GENDER_IDENTITY_OPTIONS}
              value={genderIdentity}
              onChange={setGenderIdentity}
              required
            />
          </Stack>

          <Divider />

          {/* ── More filters (collapsible) ── */}
          <Stack gap={0}>
            <Box
              onClick={() => setShowMoreFilters((v) => !v)}
              style={{ cursor: 'pointer', userSelect: 'none' }}
            >
              <Group justify="space-between" align="center" py="xs">
                <Text size="sm" fw={700} tt="uppercase" style={{ color: '#495057', letterSpacing: '0.06em' }}>
                  More filters
                </Text>
                {showMoreFilters
                  ? <IconChevronUp size={16} color="#495057" />
                  : <IconChevronDown size={16} color="#495057" />}
              </Group>
            </Box>

            <Collapse in={showMoreFilters}>
              <Stack gap="md" pt="sm">
                <DatePickerInput
                  label="Move-in date"
                  description="Listings available within 60 days of this date will be prioritised"
                  placeholder="Select date"
                  value={moveInDate}
                  onChange={setMoveInDate}
                  minDate={new Date()}
                  clearable
                />

                <Select
                  label="Lease type"
                  placeholder="Any"
                  data={LEASE_TYPE_OPTIONS}
                  value={leaseType}
                  onChange={setLeaseType}
                  clearable
                />

                <NumberInput
                  label="Lease duration (months)"
                  placeholder="e.g. 12"
                  value={leaseDuration ?? ''}
                  onChange={(v) => setLeaseDuration(v === '' ? null : Number(v))}
                  min={1}
                  max={24}
                />

                <NumberInput
                  label="Max deposit"
                  placeholder="Highest deposit you can pay"
                  value={depositAmount ?? ''}
                  onChange={(v) => setDepositAmount(v === '' ? null : Number(v))}
                  min={0}
                  prefix="$"
                />

                <Select
                  label="Furnished preference"
                  data={FURNISHED_PREF_OPTIONS}
                  value={furnishedPref}
                  onChange={(v) => setFurnishedPref(v || 'no_preference')}
                />

                <Select
                  label="Gender policy"
                  data={GENDER_POLICY_OPTIONS}
                  value={genderPolicy}
                  onChange={(v) => setGenderPolicy(v || 'mixed_ok')}
                />
              </Stack>
            </Collapse>
          </Stack>

          {/* ── Actions ── */}
          <Stack gap="sm" mt="md">
            <Button
              size="lg"
              color="teal"
              radius="md"
              fullWidth
              loading={saving}
              onClick={handleSave}
            >
              {isGuest ? 'Browse Listings' : 'Continue to Discover'}
            </Button>
            {isGuest && (
              <Button
                size="sm"
                variant="subtle"
                color="gray"
                radius="md"
                fullWidth
                component="a"
                href="/signup"
              >
                Or create a free account to save your preferences
              </Button>
            )}
          </Stack>
        </Stack>
      </Box>
    </Box>
  );
}
