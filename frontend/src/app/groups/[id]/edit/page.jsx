'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { 
  Container, 
  Title, 
  Text, 
  Button, 
  Stack, 
  Card, 
  TextInput,
  Textarea,
  NumberInput,
  Select,
  Group,
  Loader,
  Alert,
  Switch
} from '@mantine/core';
import { DateInput } from '@mantine/dates';
import { notifications } from '@mantine/notifications';
import { IconArrowLeft, IconCheck, IconAlertCircle } from '@tabler/icons-react';
import { useAuth } from '../../../contexts/AuthContext';
import { Navigation } from '../../../components/Navigation';

export default function EditGroupPage() {
  const router = useRouter();
  const params = useParams();
  const groupId = params.id;
  const { authState, getValidToken } = useAuth();
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Form state
  const [groupName, setGroupName] = useState('');
  const [description, setDescription] = useState('');
  const [targetCity, setTargetCity] = useState('');
  const [cityOptions, setCityOptions] = useState([]);
  const [citySearch, setCitySearch] = useState('');
  const [budgetMin, setBudgetMin] = useState(null);
  const [budgetMax, setBudgetMax] = useState(null);
  const [moveInDate, setMoveInDate] = useState(null);
  const [hasGroupSizeLimit, setHasGroupSizeLimit] = useState(false);
  const [groupSize, setGroupSize] = useState(2);
  const [isSolo, setIsSolo] = useState(false);

  useEffect(() => {
    const loadCities = async () => {
      try {
        const query = citySearch.trim();
        const response = await fetch(
          `${API_BASE}/api/options/cities-global?q=${encodeURIComponent(query)}&limit=200`
        );
        if (!response.ok) return;
        const result = await response.json();
        setCityOptions(result.data || []);
      } catch {
        // Keep form usable if options API is temporarily unavailable.
      }
    };
    loadCities();
  }, [citySearch]);

  // Fetch existing group data
  useEffect(() => {
    const fetchGroup = async () => {
      if (!groupId) return;
      
      try {
        const headers = {};
        if (authState?.accessToken) {
          headers['Authorization'] = `Bearer ${authState.accessToken}`;
        }
        
        const response = await fetch(`${API_BASE}/api/roommate-groups/${groupId}`, {
          headers
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
          const group = data.data;
          setGroupName(group.group_name || '');
          setDescription(group.description || '');
          setTargetCity(group.target_city || '');
          setCitySearch(group.target_city || '');
          setBudgetMin(group.budget_per_person_min || null);
          setBudgetMax(group.budget_per_person_max || null);
          setHasGroupSizeLimit(group.target_group_size != null);
          setGroupSize(group.target_group_size ?? 2);
          setIsSolo(group.is_solo || false);
          
          if (group.target_move_in_date) {
            setMoveInDate(new Date(group.target_move_in_date));
          }
        } else {
          setError(data.detail || 'Failed to load group');
        }
      } catch (err) {
        console.error('Error fetching group:', err);
        setError('Failed to load group data');
      } finally {
        setLoading(false);
      }
    };
    
    fetchGroup();
  }, [groupId, authState]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!authState?.accessToken) {
      notifications.show({
        title: 'Authentication Required',
        message: 'Please log in to edit the group',
        color: 'red',
      });
      router.push('/login');
      return;
    }

    // Validation
    if (!groupName || !targetCity) {
      notifications.show({
        title: 'Missing Information',
        message: 'Please fill in all required fields',
        color: 'red',
      });
      return;
    }

    if (budgetMin && budgetMax && budgetMin > budgetMax) {
      notifications.show({
        title: 'Invalid Budget',
        message: 'Minimum budget cannot be greater than maximum budget',
        color: 'red',
      });
      return;
    }

    if (!isSolo && hasGroupSizeLimit && !groupSize) {
      notifications.show({
        title: 'Missing Group Size',
        message: 'Set a group size or turn off the member limit',
        color: 'red',
      });
      return;
    }

    setSaving(true);

    try {
      const token = await getValidToken();
      if (!token) {
        notifications.show({
          title: 'Session Expired',
          message: 'Please log in again',
          color: 'red',
        });
        router.push('/login');
        return;
      }

      const response = await fetch(`${API_BASE}/api/roommate-groups/${groupId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          group_name: groupName,
          description: description || null,
          target_city: targetCity,
          budget_per_person_min: budgetMin,
          budget_per_person_max: budgetMax,
          target_move_in_date: moveInDate ? moveInDate.toISOString().split('T')[0] : null,
          target_group_size: isSolo ? groupSize : (hasGroupSizeLimit ? groupSize : null)
        })
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Success!',
          message: 'Group updated successfully',
          color: 'green',
          icon: <IconCheck />,
        });
        router.push(`/groups/${groupId}`);
      } else {
        throw new Error(data.detail || 'Failed to update group');
      }
    } catch (error) {
      console.error('Error updating group:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to update group. Please try again.',
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <>
        <Navigation />
        <Container size="md" py="xl">
          <Stack align="center" gap="md" style={{ minHeight: '400px', justifyContent: 'center' }}>
            <Loader size="lg" />
            <Text>Loading group...</Text>
          </Stack>
        </Container>
      </>
    );
  }

  if (error) {
    return (
      <>
        <Navigation />
        <Container size="md" py="xl">
          <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error">
            {error}
          </Alert>
          <Button mt="md" onClick={() => router.back()}>
            Go Back
          </Button>
        </Container>
      </>
    );
  }

  return (
    <>
      <Navigation />
      <Container size="md" py="xl">
        <Stack gap="xl">
          {/* Header */}
          <Group>
            <Button
              variant="subtle"
              leftSection={<IconArrowLeft size={16} />}
              onClick={() => router.back()}
            >
              Back
            </Button>
          </Group>

          <div>
            <Title order={1}>{isSolo ? 'Edit Your Solo Profile' : 'Edit Group'}</Title>
            <Text c="dimmed" mt="xs">
              {isSolo ? 'Update your solo housing preferences' : 'Update your group details'}
            </Text>
          </div>

          {/* Edit Form */}
          <Card withBorder p="xl">
            <form onSubmit={handleSubmit}>
              <Stack gap="md">
                <TextInput
                  label={isSolo ? "Profile Name" : "Group Name"}
                  placeholder={isSolo ? "e.g., My Housing Search" : "e.g., Downtown Professionals"}
                  required
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                />

                <Textarea
                  label="Description"
                  placeholder={isSolo ? "Describe what you're looking for..." : "Tell others about your group..."}
                  minRows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />

                <Select
                  label="Target City"
                  placeholder="Search and select a city"
                  required
                  data={cityOptions}
                  searchable
                  value={targetCity}
                  onChange={(value) => setTargetCity(value || '')}
                  onSearchChange={setCitySearch}
                  nothingFoundMessage="No cities found"
                />

                {!isSolo && (
                  <>
                    <Switch
                      label="Set a member limit"
                      description="Leave this off if the group should stay open with no cap."
                      checked={hasGroupSizeLimit}
                      onChange={(event) => setHasGroupSizeLimit(event.currentTarget.checked)}
                    />

                    {hasGroupSizeLimit && (
                      <NumberInput
                        label="Group Size Limit"
                        description="How many people are looking for housing together?"
                        min={2}
                        max={50}
                        value={groupSize}
                        onChange={setGroupSize}
                      />
                    )}
                  </>
                )}

                <Group grow>
                  <NumberInput
                    label="Min Budget (per person)"
                    placeholder="500"
                    prefix="$"
                    min={0}
                    value={budgetMin}
                    onChange={setBudgetMin}
                  />

                  <NumberInput
                    label="Max Budget (per person)"
                    placeholder="2000"
                    prefix="$"
                    min={0}
                    value={budgetMax}
                    onChange={setBudgetMax}
                  />
                </Group>

                <DateInput
                  label="Target Move-in Date"
                  placeholder="Select date"
                  value={moveInDate}
                  onChange={setMoveInDate}
                  minDate={new Date()}
                  clearable
                />

                <Group justify="flex-end" mt="xl">
                  <Button variant="default" onClick={() => router.back()}>
                    Cancel
                  </Button>
                  <Button type="submit" loading={saving}>
                    Save Changes
                  </Button>
                </Group>
              </Stack>
            </form>
          </Card>
        </Stack>
      </Container>
    </>
  );
}
