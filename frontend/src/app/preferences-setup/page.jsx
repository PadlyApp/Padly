'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
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
  Text,
  Title,
  ActionIcon,
  Alert,
} from '@mantine/core';
import { RangeSlider } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { notifications } from '@mantine/notifications';
import {
  IconHome,
  IconCheck,
  IconAlertCircle,
  IconMinus,
  IconPlus,
  IconChevronDown,
  IconChevronUp,
} from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const NUM_HISTOGRAM_BINS = 30;

function formatPrice(val) {
  return `$${Math.round(val).toLocaleString()}`;
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

export default function PreferencesSetupPage() {
  const { authState, isLoading: authLoading, getValidToken } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !authState?.accessToken) {
      router.push('/login');
    }
  }, [authLoading, authState, router]);

  // Location state
  const [countryOptions, setCountryOptions] = useState([]);
  const [stateOptions, setStateOptions] = useState([]);
  const [cityOptions, setCityOptions] = useState([]);
  const [stateSearch, setStateSearch] = useState('');
  const [citySearch, setCitySearch] = useState('');
  const [targetCountry, setTargetCountry] = useState(null);
  const [targetState, setTargetState] = useState(null);
  const [targetCity, setTargetCity] = useState(null);
  const [locationError, setLocationError] = useState(null);

  // Price state
  const [histogram, setHistogram] = useState({ bins: [], global_min: 0, global_max: 0, p10: 0, p90: 0 });
  const [priceRange, setPriceRange] = useState([0, 0]);
  const [histogramCapped, setHistogramCapped] = useState(false);
  const [priceSliderActive, setPriceSliderActive] = useState(false);
  const [loadingPrices, setLoadingPrices] = useState(false);

  // Rooms state
  const [bedrooms, setBedrooms] = useState(null);
  const [bathrooms, setBathrooms] = useState(null);

  // More filters state
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [moveInDate, setMoveInDate] = useState(null);
  const [leaseType, setLeaseType] = useState(null);
  const [leaseDuration, setLeaseDuration] = useState(null);
  const [depositAmount, setDepositAmount] = useState(null);
  const [furnishedPref, setFurnishedPref] = useState('no_preference');
  const [genderPolicy, setGenderPolicy] = useState('mixed_ok');

  const [saving, setSaving] = useState(false);

  // Load countries on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/options/countries`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setCountryOptions(d.data || []))
      .catch(() => {});
  }, []);

  // Load states when country changes
  useEffect(() => {
    setTargetState(null);
    setTargetCity(null);
    setStateOptions([]);
    setCityOptions([]);
    setStateSearch('');
    if (!targetCountry) return;

    fetch(`${API_BASE}/api/options/states?country_code=${encodeURIComponent(targetCountry)}`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setStateOptions(d.data || []))
      .catch(() => {});
  }, [targetCountry]);

  // Reset city when state changes
  useEffect(() => {
    setTargetCity(null);
    setCityOptions([]);
  }, [targetState]);

  // Load city options
  useEffect(() => {
    if (!targetCountry || !targetState) return;
    fetch(
      `${API_BASE}/api/options/cities?country_code=${encodeURIComponent(targetCountry)}&state_code=${encodeURIComponent(targetState)}&q=${encodeURIComponent(citySearch)}&limit=250`
    )
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setCityOptions(d.data || []))
      .catch(() => {});
  }, [targetCountry, targetState, citySearch]);

  // Fetch price histogram when city is selected
  useEffect(() => {
    if (!targetCity) {
      setHistogram({ bins: [], global_min: 0, global_max: 0, p10: 0, p90: 0 });
      setHistogramCapped(false);
      setPriceSliderActive(false);
      return;
    }

    setLoadingPrices(true);
    fetch(
      `${API_BASE}/api/listings/price-histogram?city=${encodeURIComponent(targetCity)}&status=active&bins=${NUM_HISTOGRAM_BINS}`
    )
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        const data = d?.data;
        if (data && data.total_count > 0) {
          const effectiveMax = data.display_max ?? data.global_max;
          setHistogram({ bins: data.bins, global_min: data.global_min, global_max: effectiveMax, p10: data.p10, p90: data.p90 });
          setHistogramCapped(data.capped ?? false);
          setPriceRange([data.global_min, effectiveMax]);
        } else {
          setHistogram({ bins: [], global_min: 500, global_max: 5000, p10: 500, p90: 5000 });
          setHistogramCapped(false);
          setPriceRange([500, 5000]);
        }
        setPriceSliderActive(true);
      })
      .catch(() => {
        setHistogram({ bins: [], global_min: 500, global_max: 5000, p10: 500, p90: 5000 });
        setHistogramCapped(false);
        setPriceRange([500, 5000]);
        setPriceSliderActive(true);
      })
      .finally(() => setLoadingPrices(false));
  }, [targetCity]);

  const handleSave = useCallback(async () => {
    if (!targetCountry || !targetState || !targetCity) {
      setLocationError('Please select a country, state/province, and city to continue.');
      return;
    }
    setLocationError(null);
    setSaving(true);

    try {
      const token = await getValidToken();
      if (!token) throw new Error('Not authenticated');

      const meRes = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
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

      if (moveInDate) body.move_in_date = moveInDate instanceof Date ? moveInDate.toISOString().split('T')[0] : moveInDate;
      if (leaseType) body.target_lease_type = leaseType;
      if (leaseDuration) body.target_lease_duration_months = leaseDuration;
      if (depositAmount) body.target_deposit_amount = depositAmount;
      body.furnished_preference = furnishedPref;
      body.gender_policy = genderPolicy;

      const res = await fetch(`${API_BASE}/api/preferences/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });

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
  }, [targetCountry, targetState, targetCity, priceSliderActive, priceRange, bedrooms, bathrooms, moveInDate, leaseType, leaseDuration, depositAmount, furnishedPref, genderPolicy, getValidToken, router]);

  const handleSkip = () => {
    localStorage.setItem('padly_preferences_complete', 'true');
    localStorage.setItem('padly_onboarding_complete', 'true');
    router.push('/discover');
  };

  const maxBinCount = histogram.bins.length > 0
    ? Math.max(...histogram.bins.map((b) => b.count))
    : 0;

  const sliderMin = histogram.global_min || 0;
  const sliderMax = histogram.global_max || 5000;

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

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column' }}>
      {/* Logo header */}
      <Box style={{ borderBottom: '1px solid #e9ecef', padding: '1rem 2rem', flexShrink: 0 }}>
        <Group gap="xs" align="center">
          <Box style={{ width: 28, height: 28, borderRadius: 8, background: '#20c997', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <IconHome size={16} color="white" />
          </Box>
          <Text size="lg" fw={700} style={{ color: '#212529' }}>Padly</Text>
        </Group>
      </Box>

      {/* Scrollable content */}
      <Box style={{ flex: 1, overflowY: 'auto', display: 'flex', justifyContent: 'center', padding: '2.5rem 1.5rem 4rem' }}>
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

          {/* ── Section 1: Location ── */}
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
              onChange={(val) => { setTargetCountry(val); setStateSearch(''); setCitySearch(''); setLocationError(null); }}
            />

            <Select
              label="State / Province"
              placeholder={targetCountry ? 'Search state or province' : 'Select a country first'}
              data={stateOptions}
              value={targetState}
              onChange={(val) => { setTargetState(val); setCitySearch(''); setLocationError(null); }}
              searchable
              searchValue={stateSearch}
              onSearchChange={setStateSearch}
              disabled={!targetCountry}
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
              disabled={!targetState}
              searchable
              nothingFoundMessage={targetState ? 'No cities found' : 'Select a state first'}
            />
          </Stack>

          <Divider />

          {/* ── Section 2: Price range ── */}
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
              <Box style={{ padding: '1.5rem', background: '#f8f9fa', borderRadius: 10, textAlign: 'center' }}>
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
          </Stack>

          <Divider />

          {/* ── Section 3: Rooms ── */}
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
                {showMoreFilters ? <IconChevronUp size={16} color="#495057" /> : <IconChevronDown size={16} color="#495057" />}
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
                  data={[
                    { value: 'fixed', label: 'Fixed-term lease' },
                    { value: 'month_to_month', label: 'Month-to-month' },
                    { value: 'sublet', label: 'Sublet' },
                    { value: 'any', label: 'Any' },
                  ]}
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
                  data={[
                    { value: 'required', label: 'Must be furnished' },
                    { value: 'preferred', label: 'Prefer furnished' },
                    { value: 'no_preference', label: 'No preference' },
                  ]}
                  value={furnishedPref}
                  onChange={(v) => setFurnishedPref(v || 'no_preference')}
                />

                <Select
                  label="Gender policy"
                  data={[
                    { value: 'mixed_ok', label: 'Mixed gender is okay' },
                    { value: 'same_gender_only', label: 'Same gender only' },
                  ]}
                  value={genderPolicy}
                  onChange={(v) => setGenderPolicy(v || 'mixed_ok')}
                />
              </Stack>
            </Collapse>
          </Stack>

          {/* ── Actions ── */}
          <Stack gap="sm" mt="md">
            <Button size="lg" color="teal" radius="md" fullWidth loading={saving} onClick={handleSave}>
              Continue to Discover
            </Button>
            <Button variant="subtle" color="gray" size="sm" fullWidth onClick={handleSkip}>
              Skip for now
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Box>
  );
}
