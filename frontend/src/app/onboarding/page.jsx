'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  TextInput,
  Textarea,
  Button,
  Paper,
  Title,
  Text,
  Container,
  Stack,
  Group,
  Stepper,
  Progress,
  SegmentedControl,
  Box,
  Select,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconUser, IconBriefcase, IconSchool, IconCheck, IconHome, IconSearch } from '@tabler/icons-react';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';
import { apiFetch } from '../../../lib/api';

export default function OnboardingPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [active, setActive] = useState(0);
  const [companyOptions, setCompanyOptions] = useState([]);
  const [schoolOptions, setSchoolOptions] = useState([]);
  const [roleTitleOptions, setRoleTitleOptions] = useState([]);
  const { user, authState, isLoading: authLoading, getValidToken } = useAuth();
  const { startTour } = usePadlyTour();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !authState?.accessToken) {
      router.push('/login');
    }
  }, [authLoading, authState, router]);

  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [companiesRes, schoolsRes, rolesRes] = await Promise.all([
          apiFetch(`/options/companies?limit=500`),
          apiFetch(`/options/schools?limit=500`),
          apiFetch(`/options/roles`),
        ]);

        if (companiesRes.ok) {
          const result = await companiesRes.json();
          setCompanyOptions(result.data || []);
        }
        if (schoolsRes.ok) {
          const result = await schoolsRes.json();
          setSchoolOptions(result.data || []);
        }
        if (rolesRes.ok) {
          const result = await rolesRes.json();
          setRoleTitleOptions(result.data || []);
        }
      } catch {
        // Keep onboarding usable if options service is temporarily unavailable.
      }
    };
    loadOptions();
  }, []);

  const form = useForm({
    initialValues: {
      role: 'renter',
      bio: '',
      company_name: '',
      school_name: '',
      role_title: '',
    },
    validate: {
      bio: (value) => (value.length > 500 ? 'Bio must be less than 500 characters' : null),
      role: (value) => (!value ? 'Please select a role' : null),
      school_name: (value) => (!value || !value.trim() ? 'Please enter your school/university' : null),
    },
  });

  const handleSubmit = async (values) => {
    setIsLoading(true);
    console.log('Submitting onboarding form with values:', values);

    try {
      const token = await getValidToken();
      if (!token) {
        throw new Error('Please log in to complete your profile');
      }
      console.log('Got valid token');

      // Get the user profile ID from the users table (not auth_id)
      const userResponse = await apiFetch(`/auth/me`, {}, { token });
      
      const userData = await userResponse.json();
      console.log('User data from /me:', userData);
      
      if (!userResponse.ok) {
        throw new Error(userData.detail || 'Failed to get user info');
      }

      // Use the profile id from users table, not the auth id
      const userId = userData.user?.profile?.id;
      console.log('User profile ID:', userId);
      
      if (!userId) {
        throw new Error('User profile ID not found. Please try logging out and back in.');
      }

      // Prepare update data - filter out empty strings
      const updateData = {
        role: values.role,
      };
      if (values.bio && values.bio.trim()) updateData.bio = values.bio.trim();
      if (values.company_name && values.company_name.trim()) updateData.company_name = values.company_name.trim();
      if (values.school_name && values.school_name.trim()) updateData.school_name = values.school_name.trim();
      if (values.role_title && values.role_title.trim()) updateData.role_title = values.role_title.trim();
      
      console.log('Sending update data:', updateData);

      // Update user profile
      const response = await apiFetch(
        `/users/${userId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updateData),
        },
        { token }
      );

      const data = await response.json();
      console.log('Update response:', data);

      if (response.ok && data.status === 'success') {
        notifications.show({
          title: 'Profile Complete!',
          message: 'Your profile has been updated successfully',
          color: 'green',
          icon: <IconCheck />,
        });
        
        localStorage.setItem('padly_onboarding_complete', 'true');
        startTour();
        router.push('/');
      } else {
        throw new Error(data.detail || 'Failed to update profile');
      }
    } catch (err) {
      console.error('Profile update error:', err);
      notifications.show({
        title: 'Update Failed',
        message: err.message || 'Failed to update profile. Please try again.',
        color: 'red',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCompleteProfile = () => {
    const validation = form.validate();
    if (!validation.hasErrors) {
      handleSubmit(form.values);
    }
  };

  const handleSkip = () => {
    // Mark onboarding as complete even if skipped
    localStorage.setItem('padly_onboarding_complete', 'true');
    router.push('/');
  };

  const nextStep = () => {
    let stepValid = true;

    if (active === 0) {
      stepValid = !form.validateField('role').hasError;
    }

    if (active === 1) {
      stepValid = !form.validateField('bio').hasError;
    }

    if (active === 2) {
      // work step has no required fields
      stepValid = true;
    }

    if (active === 3) {
      stepValid = !form.validateField('school_name').hasError;
    }

    if (stepValid) {
      setActive((current) => current + 1);
    }
  };
  const prevStep = () => setActive((current) => (current > 0 ? current - 1 : current));

  const progress = ((active + 1) / 5) * 100;

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {/* Hairline progress at top */}
      <Progress value={progress} size="xs" color="teal" radius={0} style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10 }} />

      {/* Logo-only top bar */}
      <Box style={{ borderBottom: '1px solid #e9ecef', padding: '1rem 2rem' }}>
        <Group gap="xs" align="center">
          <Box style={{ width: 28, height: 28, borderRadius: 8, background: '#20c997', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <IconHome size={16} color="white" />
          </Box>
          <Text size="lg" fw={700} style={{ color: '#212529' }}>Padly</Text>
        </Group>
      </Box>

      {/* Existing content */}
      <Box style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <Container size={500} my={40}>
          <Title ta="center" fw={900}>
            Complete Your Profile
          </Title>
          <Text c="dimmed" size="sm" ta="center" mt={5} mb={30}>
            Tell us a bit more about yourself to help find better roommate matches
          </Text>

          <Paper shadow="sm" radius="lg" style={{ border: '1px solid #e9ecef' }} p={30}>
          <Stepper active={active} size="sm" mb="xl" allowNextStepsSelect={false}>
            <Stepper.Step label="Role" icon={<IconHome size={18} />}>
              <Stack mt="md" gap="lg">
                <Text size="sm" fw={500}>What brings you to Padly?</Text>
                <SegmentedControl
                  fullWidth
                  size="md"
                  data={[
                    { 
                      label: (
                        <Group gap="xs" justify="center">
                          <IconSearch size={16} />
                          <span>Looking for a place</span>
                        </Group>
                      ), 
                      value: 'renter' 
                    },
                    { 
                      label: (
                        <Group gap="xs" justify="center">
                          <IconHome size={16} />
                          <span>Listing a place</span>
                        </Group>
                      ), 
                      value: 'host' 
                    },
                  ]}
                  {...form.getInputProps('role')}
                />
                <Text size="xs" c="dimmed" ta="center">
                  {form.values.role === 'renter' 
                    ? "You're looking to find a place to live and potentially roommates."
                    : "You have a property to list and are looking for tenants."}
                </Text>
              </Stack>
            </Stepper.Step>

            <Stepper.Step label="About You" icon={<IconUser size={18} />}>
              <Stack mt="md">
                <Textarea
                  label="Bio"
                  placeholder="Tell potential roommates about yourself - your interests, lifestyle, what you're looking for..."
                  minRows={4}
                  maxRows={6}
                  {...form.getInputProps('bio')}
                />
                <Text size="xs" c="dimmed" ta="right">
                  {form.values.bio.length}/500 characters
                </Text>
              </Stack>
            </Stepper.Step>

            <Stepper.Step label="Work" icon={<IconBriefcase size={18} />}>
              <Stack mt="md">
                <Select
                  label="Company Name"
                  placeholder="Select company (optional)"
                  data={companyOptions}
                  searchable
                  {...form.getInputProps('company_name')}
                />
                <Select
                  label="Role / Title"
                  placeholder="Select role/title (optional)"
                  data={roleTitleOptions}
                  searchable
                  {...form.getInputProps('role_title')}
                />
              </Stack>
            </Stepper.Step>

            <Stepper.Step label="Education" icon={<IconSchool size={18} />}>
              <Stack mt="md">
                <Select
                  label="School / University"
                  placeholder="Select school/university"
                  data={schoolOptions}
                  searchable
                  required
                  {...form.getInputProps('school_name')}
                />
              </Stack>
            </Stepper.Step>

            <Stepper.Completed>
              <Stack mt="md" gap="lg">
                <Title order={3} ta="center">Review Your Profile</Title>
                
                <Stack gap="sm">
                  <div>
                    <Text size="sm" c="dimmed">Role</Text>
                    <Text fw={500}>{form.values.role === 'renter' ? 'Looking for a place' : 'Listing a place'}</Text>
                  </div>

                  {form.values.bio && (
                    <div>
                      <Text size="sm" c="dimmed">Bio</Text>
                      <Text>{form.values.bio}</Text>
                    </div>
                  )}

                  {form.values.company_name && (
                    <div>
                      <Text size="sm" c="dimmed">Company</Text>
                      <Text fw={500}>{form.values.company_name}</Text>
                    </div>
                  )}

                  {form.values.role_title && (
                    <div>
                      <Text size="sm" c="dimmed">Role/Title</Text>
                      <Text fw={500}>{form.values.role_title}</Text>
                    </div>
                  )}

                  {form.values.school_name && (
                    <div>
                      <Text size="sm" c="dimmed">School</Text>
                      <Text fw={500}>{form.values.school_name}</Text>
                    </div>
                  )}
                </Stack>

                <Button 
                  onClick={handleCompleteProfile}
                  loading={isLoading}
                  color="teal"
                  size="lg"
                  fullWidth
                >
                  Complete Profile
                </Button>
              </Stack>
            </Stepper.Completed>
          </Stepper>

          <Group justify="space-between" mt="xl">
            {active > 0 ? (
              <Button variant="default" onClick={prevStep}>
                Back
              </Button>
            ) : (
              <Button variant="subtle" color="gray" onClick={handleSkip}>
                Skip for now
              </Button>
            )}

            {active < 4 && (
              <Button onClick={nextStep}>
                Next
              </Button>
            )}
          </Group>
          </Paper>
        </Container>
      </Box>
    </Box>
  );
}
