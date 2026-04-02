'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '${API_BASE}';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
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
  Paper,
  Stepper,
  Box,
  Switch
} from '@mantine/core';
import { DateInput } from '@mantine/dates';
import { notifications } from '@mantine/notifications';
import { IconArrowLeft, IconCheck } from '@tabler/icons-react';
import { useAuth } from '../../contexts/AuthContext';
import { Navigation } from '../../components/Navigation';

export default function CreateGroupPage() {
  const router = useRouter();
  const { user, authState, getValidToken } = useAuth();
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);

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

  const handleSubmit = async (e) => {
    console.log("we submitting baby")
    e.preventDefault();

    if (!user || !authState?.accessToken) {
      notifications.show({
        title: 'Authentication Required',
        message: 'Please log in to create a group',
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

    if (hasGroupSizeLimit && !groupSize) {
      notifications.show({
        title: 'Missing Group Size',
        message: 'Set a group size or turn off the member limit',
        color: 'red',
      });
      return;
    }

    setLoading(true);

    try {
      // Get a valid token (refreshes if expired)
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

      const response = await fetch('${API_BASE}/api/roommate-groups', {
        method: 'POST',
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
          target_group_size: hasGroupSizeLimit ? groupSize : null,
          status: 'active'
        })
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Success!',
          message: 'Group created successfully',
          color: 'green',
          icon: <IconCheck />,
        });
        router.push(`/groups/${data.data.id}`);
      } else {
        throw new Error(data.detail || 'Failed to create group');
      }
    } catch (error) {
      console.error('Error creating group:', error);
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to create group. Please try again.',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  const nextStep = () => {
    if (active === 0) {
      if (!groupName || !targetCity) {
        notifications.show({
          title: 'Missing Information',
          message: 'Please provide a group name and target city',
          color: 'orange',
        });
        return;
      }
    }
    setActive((current) => (current < 3 ? current + 1 : current));
  };

  const prevStep = () => setActive((current) => (current > 0 ? current - 1 : current));

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
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
          <Title order={1}>Create a Roommate Group</Title>
          <Text c="dimmed" mt="xs">
            Form a group to find housing together
          </Text>
        </div>

        {/* Stepper */}
        <Stepper active={active} onStepClick={setActive} breakpoint="sm">
          <Stepper.Step label="Basic Info" description="Group details">
            <Card withBorder p="xl" mt="xl">
              <Stack gap="md">
                <TextInput
                  label="Group Name"
                  placeholder="e.g., Downtown Professionals"
                  required
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                />

                <Textarea
                  label="Description"
                  placeholder="Tell others about your group..."
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
              </Stack>
            </Card>
          </Stepper.Step>

          <Stepper.Step label="Budget" description="Price range">
            <Card withBorder p="xl" mt="xl">
              <Stack gap="md">
                <Text size="sm" c="dimmed">
                  Set your budget range per person
                </Text>

                <NumberInput
                  label="Minimum Budget (per person)"
                  placeholder="500"
                  prefix="$"
                  min={0}
                  value={budgetMin}
                  onChange={setBudgetMin}
                />

                <NumberInput
                  label="Maximum Budget (per person)"
                  placeholder="2000"
                  prefix="$"
                  min={0}
                  value={budgetMax}
                  onChange={setBudgetMax}
                />

                {budgetMin && budgetMax && (
                  <Paper p="md" bg="teal.0" style={{ backgroundColor: '#e6fcf5' }}>
                    <Text size="sm" fw={500}>
                      Total Budget Range: ${budgetMin * groupSize} - ${budgetMax * groupSize}
                    </Text>
                    <Text size="xs" c="dimmed" mt={4}>
                      Based on {groupSize} people
                    </Text>
                  </Paper>
                )}
              </Stack>
            </Card>
          </Stepper.Step>

          <Stepper.Step label="Move-in Date" description="Target date">
            <Card withBorder p="xl" mt="xl">
              <Stack gap="md">
                <DateInput
                  label="Target Move-in Date"
                  placeholder="Select date"
                  value={moveInDate}
                  onChange={setMoveInDate}
                  minDate={new Date()}
                  clearable
                />

                <Text size="sm" c="dimmed">
                  This helps match you with listings available around your preferred date
                </Text>
              </Stack>
            </Card>
          </Stepper.Step>

          <Stepper.Completed>
            <Card withBorder p="xl" mt="xl">
              <Stack gap="lg">
                <Title order={3}>Review Your Group</Title>

                <Stack gap="md">
                  <div>
                    <Text size="sm" c="dimmed">Group Name</Text>
                    <Text fw={500}>{groupName}</Text>
                  </div>

                  {description && (
                    <div>
                      <Text size="sm" c="dimmed">Description</Text>
                      <Text>{description}</Text>
                    </div>
                  )}

                  <div>
                    <Text size="sm" c="dimmed">Target City</Text>
                    <Text fw={500}>{targetCity}</Text>
                  </div>

                  <div>
                    <Text size="sm" c="dimmed">Group Size</Text>
                    <Text fw={500}>{groupSize} people</Text>
                  </div>

                  {budgetMin && budgetMax && (
                    <div>
                      <Text size="sm" c="dimmed">Budget per Person</Text>
                      <Text fw={500}>${budgetMin} - ${budgetMax}</Text>
                    </div>
                  )}

                  {moveInDate && (
                    <div>
                      <Text size="sm" c="dimmed">Target Move-in Date</Text>
                      <Text fw={500}>{moveInDate.toLocaleDateString()}</Text>
                    </div>
                  )}
                </Stack>

                <Button
                  onClick={handleSubmit}
                  loading={loading}
                  size="lg"
                  fullWidth
                >
                  Create Group
                </Button>
              </Stack>
            </Card>
          </Stepper.Completed>
        </Stepper>

        {/* Navigation Buttons */}
        <Group justify="space-between" mt="xl">
          <Button variant="default" onClick={prevStep} disabled={active === 0}>
            Back
          </Button>
          {active < 3 && (
            <Button onClick={nextStep}>
              Next
            </Button>
          )}
        </Group>
      </Stack>
    </Container>
    </Box>
  );
}
