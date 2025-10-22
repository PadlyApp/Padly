'use client';

import { useState, useEffect } from 'react';
import { 
  Container, Title, Text, Stack, Box, Paper, Tabs, 
  TextInput, NumberInput, Select, Switch, Button, Group,
  MultiSelect, Grid, Divider, Loader, Alert
} from '@mantine/core';
import { Navigation } from '../components/Navigation';
import { IconHome, IconUsers, IconCheck, IconAlertCircle } from '@tabler/icons-react';

export default function PreferencesPage() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  
  
  // Housing Preferences
  const [housingPrefs, setHousingPrefs] = useState({
    // Hard Constraints
    lease_type: null,
    move_in_date: null,
    move_out_date: null,
    min_bedrooms: null,
    max_bedrooms: null,
    min_bathrooms: null,
    furnished_required: null,
    pets_allowed: null,
    smoking_allowed: null,
    parking_required: null,
    accessibility_required: null,
    
    // Soft Constraints (Amenities)
    laundry_in_unit: null,
    laundry_in_building: null,
    dishwasher: null,
    air_conditioning: null,
    heating: null,
    outdoor_space: null,
    gym_access: null,
    pool_access: null,
    storage_space: null,
    high_speed_internet: null,
    utilities_included: null,
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
  }, []);

  const loadPreferences = async () => {
    setLoading(true);
    try {
      // TODO: Replace with actual user ID from auth
      const userId = 'test-user-id';
      const response = await fetch(`http://localhost:8000/api/preferences/${userId}`);
      
      if (response.ok) {
        const result = await response.json();
        const data = result.data;
        
        if (data) {
          if (data.housing_preferences) {
            setHousingPrefs(prev => ({ ...prev, ...data.housing_preferences }));
          }
          
          if (data.roommate_preferences) {
            setRoommatePrefs(prev => ({ ...prev, ...data.roommate_preferences }));
          }
        }
      }
    } catch (err) {
      console.error('Failed to load preferences:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    
    try {
      // TODO: Replace with actual user ID from auth
      const userId = 'test-user-id';
      
      const payload = {
        housing_preferences: housingPrefs,
        roommate_preferences: roommatePrefs,
      };
      
      const response = await fetch(`http://localhost:8000/api/preferences/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          // TODO: Add Authorization header with JWT
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

  if (loading) {
    return (
      <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
        <Navigation />
        <Container size="md" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
          <Loader size="lg" />
          <Text mt="md" c="dimmed">Loading your preferences...</Text>
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
              <Tabs.Tab value="roommate" leftSection={<IconUsers size={16} />}>
                Roommate Preferences
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
                      <Select
                        label="Lease Type"
                        placeholder="Select lease type"
                        data={[
                          { value: 'fixed_term', label: 'Fixed Term' },
                          { value: 'open_ended', label: 'Open-Ended / Month-to-Month' },
                        ]}
                        value={housingPrefs.lease_type}
                        onChange={(value) => updateHousingPref('lease_type', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <TextInput
                        label="Desired Move-In Date"
                        type="date"
                        placeholder="YYYY-MM-DD"
                        value={housingPrefs.move_in_date || ''}
                        onChange={(e) => updateHousingPref('move_in_date', e.target.value || null)}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Minimum Bedrooms"
                        placeholder="e.g., 1"
                        min={0}
                        max={10}
                        value={housingPrefs.min_bedrooms}
                        onChange={(value) => updateHousingPref('min_bedrooms', value)}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Maximum Bedrooms"
                        placeholder="e.g., 3"
                        min={0}
                        max={10}
                        value={housingPrefs.max_bedrooms}
                        onChange={(value) => updateHousingPref('max_bedrooms', value)}
                      />
                    </Grid.Col>
                  </Grid>

                  <Divider my="lg" />

                  <Stack gap="md">
                    <Switch
                      label="Must be furnished"
                      checked={housingPrefs.furnished_required === true}
                      onChange={(e) => updateHousingPref('furnished_required', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Must allow pets"
                      checked={housingPrefs.pets_allowed === true}
                      onChange={(e) => updateHousingPref('pets_allowed', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="No smoking allowed (required)"
                      checked={housingPrefs.smoking_allowed === false}
                      onChange={(e) => updateHousingPref('smoking_allowed', e.currentTarget.checked ? false : null)}
                    />
                    <Switch
                      label="Parking required"
                      checked={housingPrefs.parking_required === true}
                      onChange={(e) => updateHousingPref('parking_required', e.currentTarget.checked ? true : null)}
                    />
                    <Switch
                      label="Wheelchair accessible (required)"
                      checked={housingPrefs.accessibility_required === true}
                      onChange={(e) => updateHousingPref('accessibility_required', e.currentTarget.checked ? true : null)}
                    />
                  </Stack>
                </Paper>

                <Paper shadow="sm" p="xl" radius="md" withBorder>
                  <Title order={4} mb="md">💬 Soft Preferences (Nice-to-Haves)</Title>
                  <Text size="sm" c="dimmed" mb="lg">
                    These preferences influence matching but aren't deal-breakers
                  </Text>
                  
                  <Stack gap="md">
                    <Switch
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
                    />
                    <Switch
                      label="Utilities included in rent"
                      checked={housingPrefs.utilities_included === true}
                      onChange={(e) => updateHousingPref('utilities_included', e.currentTarget.checked ? true : null)}
                    />
                  </Stack>
                </Paper>
              </Stack>
            </Tabs.Panel>

            {/* Roommate Preferences Tab */}
            <Tabs.Panel value="roommate" pt="xl">
              <Stack gap="lg">
                <Paper shadow="sm" p="xl" radius="md" withBorder>
                  <Title order={4} mb="md">👤 Demographics</Title>
                  
                  <Grid>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Minimum Age"
                        placeholder="e.g., 18"
                        min={18}
                        max={100}
                        value={roommatePrefs.age_min}
                        onChange={(value) => updateRoommatePref('age_min', value)}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <NumberInput
                        label="Maximum Age"
                        placeholder="e.g., 35"
                        min={18}
                        max={100}
                        value={roommatePrefs.age_max}
                        onChange={(value) => updateRoommatePref('age_max', value)}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Gender Preference"
                        placeholder="Select preference"
                        data={[
                          { value: 'any', label: 'Any' },
                          { value: 'male', label: 'Male' },
                          { value: 'female', label: 'Female' },
                          { value: 'non-binary', label: 'Non-binary' },
                        ]}
                        value={roommatePrefs.gender_preference}
                        onChange={(value) => updateRoommatePref('gender_preference', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <MultiSelect
                        label="Occupation Types"
                        placeholder="Select occupations"
                        data={[
                          { value: 'student', label: 'Student' },
                          { value: 'professional', label: 'Professional' },
                          { value: 'remote_worker', label: 'Remote Worker' },
                          { value: 'freelancer', label: 'Freelancer' },
                        ]}
                        value={roommatePrefs.occupation_types}
                        onChange={(value) => updateRoommatePref('occupation_types', value)}
                      />
                    </Grid.Col>
                  </Grid>
                </Paper>

                <Paper shadow="sm" p="xl" radius="md" withBorder>
                  <Title order={4} mb="md">🏠 Lifestyle Compatibility</Title>
                  
                  <Grid>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Cleanliness Level"
                        placeholder="Select level"
                        data={[
                          { value: 'very_clean', label: 'Very Clean' },
                          { value: 'moderately_clean', label: 'Moderately Clean' },
                          { value: 'relaxed', label: 'Relaxed' },
                        ]}
                        value={roommatePrefs.cleanliness_level}
                        onChange={(value) => updateRoommatePref('cleanliness_level', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Noise Tolerance"
                        placeholder="Select tolerance"
                        data={[
                          { value: 'very_quiet', label: 'Very Quiet' },
                          { value: 'quiet', label: 'Quiet' },
                          { value: 'moderate', label: 'Moderate' },
                          { value: 'lively', label: 'Lively' },
                        ]}
                        value={roommatePrefs.noise_tolerance}
                        onChange={(value) => updateRoommatePref('noise_tolerance', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Social Preference"
                        placeholder="Select preference"
                        data={[
                          { value: 'private', label: 'Private / Introverted' },
                          { value: 'occasionally_social', label: 'Occasionally Social' },
                          { value: 'social', label: 'Social' },
                          { value: 'very_social', label: 'Very Social' },
                        ]}
                        value={roommatePrefs.social_preference}
                        onChange={(value) => updateRoommatePref('social_preference', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Guest Policy"
                        placeholder="Select policy"
                        data={[
                          { value: 'no_guests', label: 'No Guests' },
                          { value: 'rarely', label: 'Rarely' },
                          { value: 'occasionally', label: 'Occasionally' },
                          { value: 'frequently', label: 'Frequently' },
                        ]}
                        value={roommatePrefs.guest_policy}
                        onChange={(value) => updateRoommatePref('guest_policy', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Work Schedule"
                        placeholder="Select schedule"
                        data={[
                          { value: 'traditional_9_to_5', label: 'Traditional 9-5' },
                          { value: 'remote', label: 'Remote / Work from Home' },
                          { value: 'night_shift', label: 'Night Shift' },
                          { value: 'flexible', label: 'Flexible' },
                          { value: 'student', label: 'Student' },
                        ]}
                        value={roommatePrefs.work_schedule}
                        onChange={(value) => updateRoommatePref('work_schedule', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Sleep Schedule"
                        placeholder="Select schedule"
                        data={[
                          { value: 'early_bird', label: 'Early Bird' },
                          { value: 'average', label: 'Average' },
                          { value: 'night_owl', label: 'Night Owl' },
                        ]}
                        value={roommatePrefs.sleep_schedule}
                        onChange={(value) => updateRoommatePref('sleep_schedule', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Cooking Frequency"
                        placeholder="Select frequency"
                        data={[
                          { value: 'daily', label: 'Daily' },
                          { value: 'often', label: 'Often' },
                          { value: 'occasionally', label: 'Occasionally' },
                          { value: 'rarely', label: 'Rarely' },
                        ]}
                        value={roommatePrefs.cooking_frequency}
                        onChange={(value) => updateRoommatePref('cooking_frequency', value)}
                        clearable
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                      <Select
                        label="Temperature Preference"
                        placeholder="Select preference"
                        data={[
                          { value: 'cool', label: 'Cool' },
                          { value: 'moderate', label: 'Moderate' },
                          { value: 'warm', label: 'Warm' },
                        ]}
                        value={roommatePrefs.temperature_preference}
                        onChange={(value) => updateRoommatePref('temperature_preference', value)}
                        clearable
                      />
                    </Grid.Col>
                  </Grid>
                </Paper>

                <Paper shadow="sm" p="xl" radius="md" withBorder>
                  <Title order={4} mb="md">🚬 Substance & Lifestyle</Title>
                  
                  <Stack gap="md">
                    <Switch
                      label="Okay with smoking"
                      checked={roommatePrefs.smoking_ok === true}
                      onChange={(e) => updateRoommatePref('smoking_ok', e.currentTarget.checked ? true : false)}
                    />
                    <Switch
                      label="Okay with alcohol"
                      checked={roommatePrefs.alcohol_ok === true}
                      onChange={(e) => updateRoommatePref('alcohol_ok', e.currentTarget.checked ? true : false)}
                    />
                    <Switch
                      label="Comfortable with pets"
                      checked={roommatePrefs.pets_ok === true}
                      onChange={(e) => updateRoommatePref('pets_ok', e.currentTarget.checked ? true : false)}
                    />
                    <Switch
                      label="I have pets"
                      checked={roommatePrefs.has_pets === true}
                      onChange={(e) => updateRoommatePref('has_pets', e.currentTarget.checked ? true : false)}
                    />
                  </Stack>

                  {roommatePrefs.has_pets && (
                    <MultiSelect
                      label="Pet Types"
                      placeholder="Select pet types"
                      data={[
                        { value: 'dog', label: 'Dog' },
                        { value: 'cat', label: 'Cat' },
                        { value: 'bird', label: 'Bird' },
                        { value: 'fish', label: 'Fish' },
                        { value: 'other', label: 'Other' },
                      ]}
                      value={roommatePrefs.pet_types}
                      onChange={(value) => updateRoommatePref('pet_types', value)}
                      mt="md"
                    />
                  )}
                </Paper>

                <Paper shadow="sm" p="xl" radius="md" withBorder>
                  <Title order={4} mb="md">🍽️ Diet & Values</Title>
                  
                  <Stack gap="md">
                    <MultiSelect
                      label="Dietary Preferences"
                      placeholder="Select preferences"
                      data={[
                        { value: 'vegetarian', label: 'Vegetarian' },
                        { value: 'vegan', label: 'Vegan' },
                        { value: 'halal', label: 'Halal' },
                        { value: 'kosher', label: 'Kosher' },
                        { value: 'pescatarian', label: 'Pescatarian' },
                        { value: 'gluten_free', label: 'Gluten-Free' },
                      ]}
                      value={roommatePrefs.dietary_preferences}
                      onChange={(value) => updateRoommatePref('dietary_preferences', value)}
                    />
                    
                    <TextInput
                      label="Languages Spoken"
                      placeholder="e.g., English, Spanish, Mandarin (comma-separated)"
                      value={(roommatePrefs.languages_spoken || []).join(', ')}
                      onChange={(e) => {
                        const value = e.target.value;
                        if (value) {
                          updateRoommatePref('languages_spoken', value.split(',').map(l => l.trim()).filter(l => l));
                        } else {
                          updateRoommatePref('languages_spoken', []);
                        }
                      }}
                    />
                    
                    <Switch
                      label="LGBTQ+ friendly"
                      checked={roommatePrefs.lgbtq_friendly === true}
                      onChange={(e) => updateRoommatePref('lgbtq_friendly', e.currentTarget.checked ? true : null)}
                    />
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

