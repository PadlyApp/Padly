'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Grid,
  Group,
  Loader,
  MultiSelect,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconAlertCircle, IconCheck } from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const AMENITY_OPTIONS = [
  { value: 'laundry', label: 'Laundry' },
  { value: 'parking', label: 'Parking' },
  { value: 'gym', label: 'Gym' },
  { value: 'ac', label: 'Air Conditioning' },
  { value: 'dishwasher', label: 'Dishwasher' },
  { value: 'elevator', label: 'Elevator' },
  { value: 'doorman', label: 'Doorman' },
  { value: 'bike_storage', label: 'Bike Storage' },
];

const BUILDING_TYPE_OPTIONS = [
  { value: 'apartment', label: 'Apartment' },
  { value: 'condo', label: 'Condo' },
  { value: 'house', label: 'House' },
  { value: 'townhouse', label: 'Townhouse' },
  { value: 'loft', label: 'Loft' },
];

function emptyToNull(value) {
  if (value == null) return null;
  const text = String(value).trim();
  return text.length ? text : null;
}

export function PreferencesForm() {
  const { user, authState, isLoading: authLoading } = useAuth();
  const { tourPhase } = usePadlyTour();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const [countryOptions, setCountryOptions] = useState([]);
  const [stateOptions, setStateOptions] = useState([]);
  const [cityOptions, setCityOptions] = useState([]);
  const [neighborhoodOptions, setNeighborhoodOptions] = useState([]);
  const [citySearch, setCitySearch] = useState('');
  const [neighborhoodSearch, setNeighborhoodSearch] = useState('');

  const [existingLifestyle, setExistingLifestyle] = useState({});

  const [hardPrefs, setHardPrefs] = useState({
    target_country: 'US',
    target_state_province: null,
    target_city: null,
    budget_min: null,
    budget_max: null,
    required_bedrooms: null,
    target_bathrooms: null,
    target_deposit_amount: null,
    furnished_preference: 'no_preference',
    gender_policy: 'mixed_ok',
    move_in_date: null,
    target_lease_type: null,
    target_lease_duration_months: null,
  });

  const [softPrefs, setSoftPrefs] = useState({
    preferred_neighborhoods: [],
    cleanliness_level: null,
    social_preference: null,
    cooking_frequency: null,
    gender_identity: null,
    amenity_priorities: [],
    building_type_preferences: [],
    target_house_rules: '',
  });

  const roomPreference = useMemo(() => {
    if (hardPrefs.required_bedrooms == null) return null;
    return Number(hardPrefs.required_bedrooms) >= 1 ? 'own' : 'share';
  }, [hardPrefs.required_bedrooms]);

  const bathroomPreference = useMemo(() => {
    if (hardPrefs.target_bathrooms == null) return null;
    return Number(hardPrefs.target_bathrooms) >= 1 ? 'own' : 'share';
  }, [hardPrefs.target_bathrooms]);

  useEffect(() => {
    loadPreferences();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, authState?.accessToken]);

  useEffect(() => {
    const loadCountries = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/options/countries`);
        if (!response.ok) return;
        const result = await response.json();
        setCountryOptions(result.data || []);
      } catch {
        // Keep page usable if options endpoint is unavailable.
      }
    };
    loadCountries();
  }, []);

  useEffect(() => {
    const country = hardPrefs.target_country;
    if (!country) {
      setStateOptions([]);
      return;
    }

    const loadStates = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/options/states?country_code=${encodeURIComponent(country)}`
        );
        if (!response.ok) return;
        const result = await response.json();
        setStateOptions(result.data || []);
      } catch {
        // Keep page usable if options endpoint is unavailable.
      }
    };
    loadStates();
  }, [hardPrefs.target_country]);

  useEffect(() => {
    const country = hardPrefs.target_country;
    const state = hardPrefs.target_state_province;
    if (!country || !state) {
      setCityOptions([]);
      return;
    }

    const loadCities = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/options/cities?country_code=${encodeURIComponent(country)}&state_code=${encodeURIComponent(state)}&q=${encodeURIComponent(citySearch)}&limit=250`
        );
        if (!response.ok) return;
        const result = await response.json();
        setCityOptions(result.data || []);
      } catch {
        // Keep page usable if options endpoint is unavailable.
      }
    };
    loadCities();
  }, [hardPrefs.target_country, hardPrefs.target_state_province, citySearch]);

  useEffect(() => {
    const city = hardPrefs.target_city;
    if (!city) {
      setNeighborhoodOptions([]);
      return;
    }

    const loadNeighborhoods = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/options/neighborhoods?city=${encodeURIComponent(city)}&q=${encodeURIComponent(neighborhoodSearch)}&limit=250`
        );
        if (!response.ok) return;
        const result = await response.json();
        setNeighborhoodOptions(result.data || []);
      } catch {
        // Keep page usable if options endpoint is unavailable.
      }
    };
    loadNeighborhoods();
  }, [hardPrefs.target_city, neighborhoodSearch]);

  const updateHard = (key, value) => {
    setHardPrefs((prev) => ({ ...prev, [key]: value }));
  };

  const updateSoft = (key, value) => {
    setSoftPrefs((prev) => ({ ...prev, [key]: value }));
  };

  const loadPreferences = async () => {
    const userId = user?.profile?.id;
    if (!userId || !authState?.accessToken) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/preferences/${userId}`, {
        headers: {
          Authorization: `Bearer ${authState.accessToken}`,
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) throw new Error('Failed to load preferences');

      const result = await response.json();
      const data = result.data || {};
      const lifestyle = data.lifestyle_preferences || {};

      setExistingLifestyle(lifestyle);

      // Pre-seed city options with the saved city so the Select renders it correctly
      if (data.target_city) {
        setCityOptions([{ value: data.target_city, label: data.target_city }]);
      }

      setHardPrefs((prev) => ({
        ...prev,
        target_country: data.target_country || 'US',
        target_state_province: data.target_state_province || null,
        target_city: data.target_city || null,
        budget_min: data.budget_min ?? null,
        budget_max: data.budget_max ?? null,
        required_bedrooms: data.required_bedrooms ?? null,
        target_bathrooms: data.target_bathrooms ?? null,
        target_deposit_amount: data.target_deposit_amount ?? null,
        furnished_preference: data.furnished_preference || 'no_preference',
        gender_policy: data.gender_policy || 'mixed_ok',
        move_in_date: data.move_in_date || null,
        target_lease_type: data.target_lease_type || null,
        target_lease_duration_months: data.target_lease_duration_months ?? null,
      }));

      setSoftPrefs((prev) => ({
        ...prev,
        preferred_neighborhoods: Array.isArray(data.preferred_neighborhoods)
          ? data.preferred_neighborhoods
          : [],
        cleanliness_level: lifestyle.cleanliness_level || null,
        social_preference: lifestyle.social_preference || null,
        cooking_frequency: lifestyle.cooking_frequency || null,
        gender_identity: lifestyle.gender_identity || null,
        amenity_priorities: Array.isArray(lifestyle.amenity_priorities) ? lifestyle.amenity_priorities : [],
        building_type_preferences: Array.isArray(lifestyle.building_type_preferences)
          ? lifestyle.building_type_preferences
          : [],
        target_house_rules: data.target_house_rules || '',
      }));
    } catch (err) {
      setError(err.message || 'Failed to load preferences');
    } finally {
      setLoading(false);
    }
  };

  const buildLifestylePayload = () => {
    const merged = { ...existingLifestyle };

    const valueMap = {
      cleanliness_level: softPrefs.cleanliness_level,
      social_preference: softPrefs.social_preference,
      cooking_frequency: softPrefs.cooking_frequency,
      gender_identity: softPrefs.gender_identity,
    };

    Object.entries(valueMap).forEach(([key, value]) => {
      if (value == null || value === '') {
        delete merged[key];
      } else {
        merged[key] = value;
      }
    });

    if (softPrefs.amenity_priorities?.length) {
      merged.amenity_priorities = softPrefs.amenity_priorities;
    } else {
      delete merged.amenity_priorities;
    }

    if (softPrefs.building_type_preferences?.length) {
      merged.building_type_preferences = softPrefs.building_type_preferences;
    } else {
      delete merged.building_type_preferences;
    }

    return merged;
  };

  const handleSave = async () => {
    const userId = user?.profile?.id;
    if (!userId || !authState?.accessToken) {
      setError('You must be logged in to save preferences.');
      return;
    }

    if (!hardPrefs.target_country || !hardPrefs.target_state_province || !hardPrefs.target_city) {
      setError('Please choose country, state/province, and city.');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      const payload = {
        ...hardPrefs,
        target_house_rules: emptyToNull(softPrefs.target_house_rules),
        preferred_neighborhoods: softPrefs.preferred_neighborhoods || [],
        lifestyle_preferences: buildLifestylePayload(),
      };

      const response = await fetch(`${API_BASE}/api/preferences/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save preferences');
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);

      if (tourPhase === 'preferences') {
        window.dispatchEvent(new CustomEvent('padly-tour-prefs-saved'));
      }
    } catch (err) {
      setError(err.message || 'Network error. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || loading) {
    return (
      <Stack align="center" gap="md" py="xl" style={{ minHeight: '300px', justifyContent: 'center' }}>
        <Loader size="lg" />
        <Text c="dimmed">
          {authLoading ? 'Checking authentication...' : 'Loading your preferences...'}
        </Text>
      </Stack>
    );
  }

  return (
    <Stack gap="xl">
      <Stack align="center" gap="lg">
        <Title
          order={2}
          style={{ fontSize: '1.8rem', fontWeight: 500, color: '#111', textAlign: 'center' }}
        >
          Personal Preferences
        </Title>
        <Text size="md" c="dimmed" style={{ maxWidth: '46rem', textAlign: 'center' }}>
          Hard constraints filter listings. Soft constraints rank matches and help form compatible groups.
        </Text>
      </Stack>

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

      <Paper shadow="sm" p="xl" radius="md" withBorder data-tour="prefs-hard">
        <Title order={4} mb="md">
          Hard Constraints
        </Title>
        <Text size="sm" c="dimmed" mb="lg">
          Must-pass requirements for your housing match.
        </Text>

        <Grid>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Select
              label="Country"
              placeholder="Select country"
              data={countryOptions}
              value={hardPrefs.target_country}
              onChange={(v) => {
                updateHard('target_country', v);
                updateHard('target_state_province', null);
                updateHard('target_city', null);
                updateSoft('preferred_neighborhoods', []);
                setCitySearch('');
                setNeighborhoodSearch('');
              }}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Select
              label="State / Province"
              placeholder="Select state/province"
              data={stateOptions}
              value={hardPrefs.target_state_province}
              onChange={(v) => {
                updateHard('target_state_province', v);
                updateHard('target_city', null);
                updateSoft('preferred_neighborhoods', []);
                setCitySearch('');
                setNeighborhoodSearch('');
              }}
              searchable
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Select
              label="City"
              placeholder={hardPrefs.target_state_province ? 'Search city' : 'Select state/province first'}
              data={cityOptions}
              value={hardPrefs.target_city}
              onChange={(v) => {
                updateHard('target_city', v);
                updateSoft('preferred_neighborhoods', []);
                setNeighborhoodSearch('');
              }}
              searchable
              searchValue={citySearch}
              onSearchChange={setCitySearch}
              disabled={!hardPrefs.target_state_province}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <NumberInput
              label="Max Monthly Budget (Your Share)"
              placeholder="Maximum monthly amount"
              value={hardPrefs.budget_max}
              onChange={(v) => updateHard('budget_max', v)}
              min={0}
              prefix="$"
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <NumberInput
              label="Min Monthly Budget (Optional)"
              placeholder="Minimum monthly amount"
              value={hardPrefs.budget_min}
              onChange={(v) => updateHard('budget_min', v)}
              min={0}
              prefix="$"
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <Select
              label="Room Preference"
              description="Your room arrangement in the unit"
              data={[
                { value: 'share', label: 'Share a room' },
                { value: 'own', label: 'Have my own room' },
              ]}
              value={roomPreference}
              onChange={(v) => {
                if (v === 'own') updateHard('required_bedrooms', 1);
                else if (v === 'share') updateHard('required_bedrooms', 0);
                else updateHard('required_bedrooms', null);
              }}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <Select
              label="Bathroom Preference"
              description="Your bathroom arrangement in the unit"
              data={[
                { value: 'share', label: 'Share a bathroom' },
                { value: 'own', label: 'Have my own bathroom' },
              ]}
              value={bathroomPreference}
              onChange={(v) => {
                if (v === 'own') updateHard('target_bathrooms', 1);
                else if (v === 'share') updateHard('target_bathrooms', 0.5);
                else updateHard('target_bathrooms', null);
              }}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <NumberInput
              label="Max Deposit You Can Pay"
              placeholder="Highest acceptable deposit"
              value={hardPrefs.target_deposit_amount}
              onChange={(v) => updateHard('target_deposit_amount', v)}
              min={0}
              prefix="$"
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <Select
              label="Furnished Requirement"
              description="Required is hard-filtered; preferred only boosts ranking"
              data={[
                { value: 'required', label: 'Required' },
                { value: 'preferred', label: 'Preferred' },
                { value: 'no_preference', label: 'No preference' },
              ]}
              value={hardPrefs.furnished_preference}
              onChange={(v) => updateHard('furnished_preference', v)}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <Select
              label="Gender Policy"
              description="Used as a hard filter for group compatibility"
              data={[
                { value: 'mixed_ok', label: 'Mixed gender is okay' },
                { value: 'same_gender_only', label: 'Same gender only' },
              ]}
              value={hardPrefs.gender_policy}
              onChange={(v) => updateHard('gender_policy', v)}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <DatePickerInput
              label="Move-in Date"
              placeholder="Select date"
              value={hardPrefs.move_in_date ? new Date(hardPrefs.move_in_date) : null}
              onChange={(date) => updateHard('move_in_date', date ? date.toISOString().split('T')[0] : null)}
              minDate={new Date()}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <Select
              label="Lease Type"
              placeholder="Select lease type"
              data={[
                { value: 'fixed', label: 'Fixed-term lease' },
                { value: 'month_to_month', label: 'Month-to-month' },
                { value: 'sublet', label: 'Sublet' },
                { value: 'any', label: 'Any type' },
              ]}
              value={hardPrefs.target_lease_type}
              onChange={(v) => updateHard('target_lease_type', v)}
              required
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <NumberInput
              label="Lease Duration (Months)"
              placeholder="e.g. 12"
              value={hardPrefs.target_lease_duration_months}
              onChange={(v) => updateHard('target_lease_duration_months', v)}
              min={1}
              max={24}
              required
            />
          </Grid.Col>
        </Grid>
      </Paper>

      <Paper shadow="sm" p="xl" radius="md" withBorder data-tour="prefs-soft">
        <Title order={4} mb="md">
          Soft Constraints
        </Title>
        <Text size="sm" c="dimmed" mb="lg">
          Used for ranking and group compatibility only.
        </Text>

        <Grid>
          <Grid.Col span={{ base: 12, md: 6 }}>
            <MultiSelect
              label="Preferred Neighborhoods"
              placeholder={hardPrefs.target_city ? 'Pick neighborhoods' : 'Select city first'}
              data={neighborhoodOptions}
              value={softPrefs.preferred_neighborhoods}
              onChange={(v) => updateSoft('preferred_neighborhoods', v)}
              searchable
              searchValue={neighborhoodSearch}
              onSearchChange={setNeighborhoodSearch}
              disabled={!hardPrefs.target_city}
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Select
              label="Cleanliness"
              placeholder="Select"
              data={[
                { value: 'low', label: 'Low' },
                { value: 'moderate', label: 'Moderate' },
                { value: 'high', label: 'High' },
              ]}
              value={softPrefs.cleanliness_level}
              onChange={(v) => updateSoft('cleanliness_level', v)}
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Select
              label="Social Style"
              placeholder="Select"
              data={[
                { value: 'quiet', label: 'Quiet' },
                { value: 'balanced', label: 'Balanced' },
                { value: 'social', label: 'Social' },
              ]}
              value={softPrefs.social_preference}
              onChange={(v) => updateSoft('social_preference', v)}
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Select
              label="Cooking Frequency"
              placeholder="Select"
              data={[
                { value: 'rarely', label: 'Rarely' },
                { value: 'sometimes', label: 'Sometimes' },
                { value: 'often', label: 'Often' },
              ]}
              value={softPrefs.cooking_frequency}
              onChange={(v) => updateSoft('cooking_frequency', v)}
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <Select
              label="Gender Identity"
              description="Needed only if your hard policy is same-gender-only"
              placeholder="Select"
              data={[
                { value: 'woman', label: 'Woman' },
                { value: 'man', label: 'Man' },
                { value: 'non_binary', label: 'Non-binary' },
                { value: 'other', label: 'Other' },
              ]}
              value={softPrefs.gender_identity}
              onChange={(v) => updateSoft('gender_identity', v)}
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <MultiSelect
              label="Amenity Priorities (Top 3)"
              placeholder="Select up to 3"
              data={AMENITY_OPTIONS}
              value={softPrefs.amenity_priorities}
              onChange={(v) => updateSoft('amenity_priorities', v)}
              maxValues={3}
            />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <MultiSelect
              label="Building Type Preferences"
              placeholder="Select preferred building types"
              data={BUILDING_TYPE_OPTIONS}
              value={softPrefs.building_type_preferences}
              onChange={(v) => updateSoft('building_type_preferences', v)}
            />
          </Grid.Col>

          <Grid.Col span={12}>
            <Textarea
              label="Optional House Rules / Notes"
              placeholder="Anything important for matching, like guest expectations or shared-space rules"
              value={softPrefs.target_house_rules}
              onChange={(e) => updateSoft('target_house_rules', e.currentTarget.value)}
              minRows={3}
              maxRows={6}
            />
          </Grid.Col>
        </Grid>
      </Paper>

      <Box
        style={{
          position: 'sticky',
          bottom: 0,
          backgroundColor: 'white',
          padding: '1.5rem 0',
          borderTop: '1px solid #f1f1f1',
          marginTop: '2rem',
        }}
      >
        <Group justify="center" data-tour="prefs-save">
          <Button size="lg" onClick={handleSave} loading={saving} disabled={saving} style={{ minWidth: '220px' }}>
            Save Preferences
          </Button>
        </Group>
      </Box>
    </Stack>
  );
}
