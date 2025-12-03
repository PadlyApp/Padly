'use client';

import { useState, useEffect } from 'react';
import { 
  Container, Title, Text, Stack, Box, Paper, Tabs, 
  TextInput, NumberInput, Select, Switch, Button, Group,
  MultiSelect, Grid, Divider, Loader, Alert, Textarea
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { useAuth } from '../contexts/AuthContext';
import { IconHome, IconUsers, IconCheck, IconAlertCircle } from '@tabler/icons-react';

export default function PreferencesPage() {
  return (
    <ProtectedRoute>
      <PreferencesPageContent />
    </ProtectedRoute>
  );
}

function PreferencesPageContent() {
  const { user, authState, isLoading: authLoading } = useAuth();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Debug: Log auth state changes
  useEffect(() => {
    console.log('Auth state changed:', { 
      authLoading,
      hasUser: !!user, 
      hasProfile: !!user?.profile,
      profileId: user?.profile?.id,
      hasToken: !!authState?.accessToken 
    });
  }, [user, authState, authLoading]);
  
  
  // Housing Preferences
  const [housingPrefs, setHousingPrefs] = useState({
    // Hard Constraints
    target_city: null,
    target_state_province: null,
    budget_min: null,
    budget_max: null,
    required_bedrooms: null,
    move_in_date: null,
    target_lease_type: null,
    target_lease_duration_months: null,
    
    // Soft Preferences
    target_bathrooms: null,
    target_furnished: null,
    target_utilities_included: null,
    target_deposit_amount: null,
    target_house_rules: null,
  });
  
  // Roommate Preferences
  const [roommatePrefs, setRoommatePrefs] = useState({
    // Demographics
    age_min: null,
    age_max: null,
    gender_preference: null,
    occupation_types: [],
    
    // Lifestyle
    cleanliness_level: null,
    noise_tolerance: null,
    social_preference: null,
    guest_policy: null,
    work_schedule: null,
    sleep_schedule: null,
    cooking_frequency: null,
    temperature_preference: null,
    
    // Substance & Lifestyle
    smoking_ok: null,
    alcohol_ok: null,
    pets_ok: null,
    has_pets: null,
    pet_types: [],
    
    // Diet & Values
    dietary_preferences: [],
    languages_spoken: [],
    lgbtq_friendly: null,
  });

  // Load preferences on mount
  useEffect(() => {
    loadPreferences();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, authState]);

  const loadPreferences = async () => {
    // MUST use profile.id (database user ID), not user.id (auth ID)
    // TEMPORARY: If profile is missing, we can't load preferences
    const userId = user?.profile?.id;
    
    if (!user?.profile) {
      console.error('User profile is missing! This user needs to be recreated in the database.');
      setError('Your user profile is incomplete. Please contact support or try logging out and signing up again.');
      setLoading(false);
      return;
    }
    
    if (!userId || !authState?.accessToken) {
      console.log('Cannot load preferences:', { 
        hasUserId: !!userId, 
        hasToken: !!authState?.accessToken,
        user: user,
        profile: user?.profile
      });
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/preferences/${userId}`, {
        headers: {
          'Authorization': `Bearer ${authState.accessToken}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (response.ok) {
        const result = await response.json();
        const data = result.data;
        
        if (data) {
          // Backend returns preferences fields directly in data (not nested)
          // Extract the 13 preference fields
          const housingPrefsData = {
            // Hard Constraints
            target_city: data.target_city,
            target_state_province: data.target_state_province,
            budget_min: data.budget_min,
            budget_max: data.budget_max,
            required_bedrooms: data.required_bedrooms,
            move_in_date: data.move_in_date,
            target_lease_type: data.target_lease_type,
            target_lease_duration_months: data.target_lease_duration_months,
            // Soft Preferences
            target_bathrooms: data.target_bathrooms,
            target_furnished: data.target_furnished,
            target_utilities_included: data.target_utilities_included,
            target_deposit_amount: data.target_deposit_amount,
            target_house_rules: data.target_house_rules,
          };
          
          setHousingPrefs(prev => ({ ...prev, ...housingPrefsData }));
          
          // Note: Roommate preferences are not persisted on backend,
          // they're frontend-only for now per team decision
        }
      }
    } catch (err) {
      console.error('Failed to load preferences:', err);
      setError('Failed to load preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    // MUST use profile.id (database user ID), not user.id (auth ID)
    const userId = user?.profile?.id;
    
    if (!user?.profile) {
      setError('Your user profile is incomplete. Please log out and sign up again, or contact support.');
      console.error('User profile missing:', user);
      return;
    }
    
    if (!userId || !authState?.accessToken) {
      console.error('Save failed - missing auth:', { 
        hasUserId: !!userId, 
        hasToken: !!authState?.accessToken,
        user: user,
        profile: user?.profile
      });
      setError('You must be logged in to save preferences. Please refresh the page and try again.');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(false);
    
    try {
      
      const payload = housingPrefs;
      
      const response = await fetch(`http://localhost:8000/api/preferences/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify(payload),
      });
      
      if (response.ok) {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to save preferences');
      }
    } catch (err) {
      setError('Network error. Please try again.');
      console.error('Save error:', err);
    } finally {
      setSaving(false);
    }
  };

  const updateHousingPref = (key, value) => {
    setHousingPrefs(prev => ({ ...prev, [key]: value }));
  };

  const updateRoommatePref = (key, value) => {
    setRoommatePrefs(prev => ({ ...prev, [key]: value }));
  };

  // Show loading while auth is initializing
  if (authLoading || loading) {
    return (
      <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
        <Navigation />
        <Container size="md" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
          <Loader size="lg" />
          <Text mt="md" c="dimmed">
            {authLoading ? 'Checking authentication...' : 'Loading your preferences...'}
          </Text>
        </Container>
      </Box>
    );
  }

  // Show error if no user after auth loading is complete
  if (!authLoading && !user) {
    return (
      <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
        <Navigation />
        <Container size="md" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
          <Alert color="red" title="Authentication Required">
            Please log in to access your preferences.
          </Alert>
        </Container>
      </Box>
    );
  }

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />
      
      <Container size="lg" style={{ paddingTop: '4rem', paddingLeft: '2rem', paddingRight: '2rem', paddingBottom: '6rem' }}>
        <Stack gap="xl">
          {/* Header */}
          <Stack align="center" gap="lg">
            <Title 
              order={1} 
              style={{ 
                fontSize: '2.5rem', 
                fontWeight: 500,
                color: '#111',
                textAlign: 'center'
              }}
            >
              Set Your Preferences
            </Title>
            <Text 
              size="lg" 
              c="dimmed" 
              style={{ 
                maxWidth: '42rem', 
                textAlign: 'center',
                color: '#666'
              }}
            >
              Help us find your perfect match by setting your housing and roommate preferences
            </Text>
          </Stack>

          {/* Alerts */}
          {success && (
            <Alert icon={<IconCheck size={16} />} title="Success" color="green">
              Your preferences have been saved successfully!
            </Alert>
          )}
          
          {error && (
            <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
              {error}
            </Alert>
          )}

          {/* Tabbed Sections */}
          <Tabs defaultValue="housing" variant="pills">
            <Tabs.List grow>
              <Tabs.Tab value="housing" leftSection={<IconHome size={16} />}>
                Housing Preferences
              </Tabs.Tab>
            </Tabs.List>

            {/* Housing Preferences Tab */}
            <Tabs.Panel value="housing" pt="xl">
              <Stack gap="lg">
                <Paper shadow="sm" p="xl" radius="md" withBorder>
                  <Title order={4} mb="md">🧱 Hard Constraints (Non-Negotiables)</Title>
                  <Text size="sm" c="dimmed" mb="lg">
                    These are absolute requirements that must be met
                  </Text>
                  
                  <Grid>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <TextInput
                        label="Target City"
                        placeholder="e.g., Toronto"
                        value={housingPrefs.target_city}
                        onChange={(e) => updateHousingPref('target_city', e.currentTarget.value)}
                        required
                      />
                    </Grid.Col>
                  
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <TextInput
                        label="State/Province"
                        placeholder="e.g., Ontario, CA"
                        value={housingPrefs.target_state_province}
                        onChange={(e) => updateHousingPref('target_state_province', e.currentTarget.value)}
                        required
                      />
                    </Grid.Col>

                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Min Budget (Total)"
                        placeholder="Minimum total budget"
                        value={housingPrefs.budget_min}
                        onChange={(v) => updateHousingPref('budget_min', v)}
                        min={0}
                        prefix="$"
                        required
                      />
                    </Grid.Col>
                  
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Max Budget (Total)"
                        placeholder="Maximum total budget"
                        value={housingPrefs.budget_max}
                        onChange={(v) => updateHousingPref('budget_max', v)}
                        min={0}
                        prefix="$"
                        required
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Required Bedrooms"
                        placeholder="Exact number needed"
                        value={housingPrefs.required_bedrooms}
                        onChange={(v) => updateHousingPref('required_bedrooms', v)}
                        min={1}
                        max={10}
                        required
                      />
                    </Grid.Col>
                    
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <DatePickerInput
                        label="Target Move-in Date"
                        placeholder="Select date"
                        value={housingPrefs.move_in_date ? new Date(housingPrefs.move_in_date) : null}
                        onChange={(date) => updateHousingPref('move_in_date', date ? date.toISOString().split('T')[0] : null)}
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
                          { value: 'any', label: 'Any type' }
                        ]}
                        value={housingPrefs.target_lease_type}
                        onChange={(v) => updateHousingPref('target_lease_type', v)}
                        required
                      />
                    </Grid.Col>
                  
                  <div></div> {/* Empty cell for grid alignment */}
                    {/* <Grid.Col span={{ base: 12, md: 3 }}>
                      <NumberInput
                        label="Min Lease Duration (months)"
                        placeholder="Minimum months"
                        value={housingPrefs.min_lease_duration_months}
                        onChange={(v) => updateHousingPref('min_lease_duration_months', v)}
                        min={1}
                        max={24}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 3 }}>
                      <NumberInput
                        label="Max Lease Duration (months)"
                        placeholder="Maximum months"
                        value={housingPrefs.max_lease_duration_months}
                        onChange={(v) => updateHousingPref('max_lease_duration_months', v)}
                        min={1}
                        max={24}
                      />
                    </Grid.Col> */}
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Lease Duration (months)"
                        placeholder="Duration"
                        value={housingPrefs.target_lease_duration_months}
                        onChange={(v) => updateHousingPref('target_lease_duration_months', v)}
                        min={1}
                        max={24}
                      />
                    </Grid.Col>
                  </Grid>
                </Paper>
         
                <Paper shadow="sm" p="xl" radius="md" withBorder>
                  <Title order={4} mb="md">💬 Soft Preferences (Nice-to-Haves)</Title>
                  <Text size="sm" c="dimmed" mb="lg">
                    These preferences influence matching but aren't deal-breakers
                  </Text>
                  
                  <Stack gap="md">
                    <Grid>
                      <Grid.Col span={{ base: 12, md: 6 }}>
                        <NumberInput
                          label="Minimum Bathrooms"
                          placeholder="e.g., 1"
                          value={housingPrefs.target_bathrooms}
                          onChange={(v) => updateHousingPref('target_bathrooms', v)}
                          min={1}
                          max={10}
                          step={0.5}
                        />
                      </Grid.Col>
                      <Grid.Col span={{ base: 12, md: 6 }}>
                        <NumberInput
                          label="Min Deposit Amount"
                          placeholder="Minimum acceptable deposit"
                          value={housingPrefs.target_deposit_amount}
                          onChange={(v) => updateHousingPref('target_deposit_amount', v)}
                          min={0}
                          prefix="$"
                        />
                      </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Switch
                        label="Furnished Preference"
                        checked={housingPrefs.target_furnished === true}
                        onChange={(e) => updateHousingPref('target_furnished', e.currentTarget.checked ? true : null)}
                      />
                    </Grid.Col>
                      <Grid.Col span={{ base: 12, md: 6 }}>
                      <Switch
                        label="Utilities included in rent"
                        checked={housingPrefs.target_utilities_included === true}
                        onChange={(e) => updateHousingPref('target_utilities_included', e.currentTarget.checked ? true : null)}
                      />
                      </Grid.Col>
                    </Grid>
                    <Divider my="lg" />
                      <Title order={5} mb="md">🏠 House Rules & Lifestyle</Title>
                      <Text size="sm" c="dimmed" mb="md">
                        Describe any house rules or lifestyle preferences that matter to you
                      </Text>
                      
                      <Stack gap="md">
                        <Textarea
                          label="House Rules & Lifestyle Preferences"
                          placeholder="E.g., smoking policy, pet preferences, noise level, etc."
                          value={housingPrefs.target_house_rules || ''}
                          onChange={(e) => updateHousingPref('target_house_rules', e.currentTarget.value)}
                          minRows={3}
                          maxRows={6}
                        />
                      </Stack>
                    {/* <Switch
                      label="Laundry in unit"
                      checked={housingPrefs.laundry_in_unit === true}
                      onChange={(e) => updateHousingPref('laundry_in_unit', e.currentTarget.checked ? true : null)}
                    /> 
                    <Switch
                      label="Laundry in building"
                      checked={housingPrefs.laundry_in_building === true}
                      onChange={(e) => updateHousingPref('laundry_in_building', e.currentTarget.checked ? true : null)}
                    />
                    
                    <Switch
                      label="Dishwasher"
                      checked={housingPrefs.dishwasher === true}
                      onChange={(e) => updateHousingPref('dishwasher', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Air conditioning"
                      checked={housingPrefs.air_conditioning === true}
                      onChange={(e) => updateHousingPref('air_conditioning', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Central heating"
                      checked={housingPrefs.heating === true}
                      onChange={(e) => updateHousingPref('heating', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Outdoor space (balcony/patio/yard)"
                      checked={housingPrefs.outdoor_space === true}
                      onChange={(e) => updateHousingPref('outdoor_space', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Gym access"
                      checked={housingPrefs.gym_access === true}
                      onChange={(e) => updateHousingPref('gym_access', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Pool access"
                      checked={housingPrefs.pool_access === true}
                      onChange={(e) => updateHousingPref('pool_access', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Extra storage space"
                      checked={housingPrefs.storage_space === true}
                      onChange={(e) => updateHousingPref('storage_space', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="High-speed internet"
                      checked={housingPrefs.high_speed_internet === true}
                      onChange={(e) => updateHousingPref('high_speed_internet', e.currentTarget.checked ? true : null)}
                    />*/}
                    
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>
          </Tabs>

          {/* Save Button */}
          <Box style={{ 
            position: 'sticky', 
            bottom: 0, 
            backgroundColor: 'white',
            padding: '1.5rem 0',
            borderTop: '1px solid #f1f1f1',
            marginTop: '2rem'
          }}>
            <Group justify="center">
              <Button 
                size="lg" 
                onClick={handleSave}
                loading={saving}
                disabled={saving}
            style={{ 
                  minWidth: '200px'
                }}
              >
                Save Preferences
              </Button>
            </Group>
          </Box>
        </Stack>
      </Container>
    </Box>
  );
}


