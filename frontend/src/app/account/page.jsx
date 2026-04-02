'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Container,
  Title,
  Text,
  Stack,
  Box,
  TextInput,
  Textarea,
  Select,
  Button,
  Card,
  Group,
  Avatar,
  Loader,
  Alert,
  Divider,
  Badge,
  Tabs,
} from '@mantine/core';
import {
  IconUser,
  IconBuilding,
  IconSchool,
  IconBriefcase,
  IconCheck,
  IconAlertCircle,
  IconMail,
  IconShield,
  IconSettings,
} from '@tabler/icons-react';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { PreferencesForm } from '../components/PreferencesForm';
import { useAuth } from '../contexts/AuthContext';

function AccountTabs() {
  const searchParams = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState(tabFromUrl === 'preferences' ? 'preferences' : 'profile');

  useEffect(() => {
    const t = searchParams.get('tab');
    if (t === 'preferences') setActiveTab('preferences');
  }, [searchParams]);

  return (
    <Tabs value={activeTab} onChange={setActiveTab}>
      <Tabs.List mb="xl">
        <Tabs.Tab value="profile" leftSection={<IconUser size={16} />}>
          Profile
        </Tabs.Tab>
        <Tabs.Tab value="preferences" leftSection={<IconSettings size={16} />}>
          Preferences
        </Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="profile">
        <ProfilePanel />
      </Tabs.Panel>

      <Tabs.Panel value="preferences">
        <PreferencesForm />
      </Tabs.Panel>
    </Tabs>
  );
}

export default function AccountPage() {
  return (
    <ProtectedRoute>
      <AccountPageContent />
    </ProtectedRoute>
  );
}

function AccountPageContent() {
  return (
    <Box style={{ minHeight: '100vh' }}>
      <Navigation />

      <Container size="lg" py="xl">
        <Stack gap="xl">
          <Stack align="center" gap="md">
            <Title order={1}>Your Account</Title>
          </Stack>

          <Suspense fallback={<Loader />}>
            <AccountTabs />
          </Suspense>
        </Stack>
      </Container>
    </Box>
  );
}

function ProfilePanel() {
  const { authState, getValidToken } = useAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [companyOptions, setCompanyOptions] = useState([]);
  const [schoolOptions, setSchoolOptions] = useState([]);
  const [roleTitleOptions, setRoleTitleOptions] = useState([]);

  const [userData, setUserData] = useState({
    id: '',
    email: '',
    full_name: '',
    bio: '',
    company_name: '',
    school_name: '',
    role_title: '',
    verification_status: 'unverified',
    profile_picture_url: '',
  });

  useEffect(() => {
    const fetchUserData = async () => {
      if (!authState?.accessToken) return;

      try {
        const token = await getValidToken();
        const response = await fetch(`${API_BASE}/api/auth/me`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        const data = await response.json();

        if (response.ok && data.user) {
          const profile = data.user.profile || {};
          setUserData({
            id: profile.id ?? '',
            email: data.user.email ?? profile.email ?? '',
            full_name: profile.full_name ?? '',
            bio: profile.bio ?? '',
            company_name: profile.company_name ?? '',
            school_name: profile.school_name ?? '',
            role_title: profile.role_title ?? '',
            verification_status: profile.verification_status ?? 'unverified',
            profile_picture_url: profile.profile_picture_url ?? '',
          });
        } else {
          setError('Failed to load account data');
        }
      } catch (err) {
        console.error('Error fetching user data:', err);
        setError('Failed to load account data');
      } finally {
        setLoading(false);
      }
    };

    fetchUserData();
  }, [authState, getValidToken]);

  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [companiesRes, schoolsRes, rolesRes] = await Promise.all([
          fetch(`${API_BASE}/api/options/companies?limit=500`),
          fetch(`${API_BASE}/api/options/schools?limit=500`),
          fetch(`${API_BASE}/api/options/roles`),
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
        // Keep account page usable if options API is temporarily unavailable.
      }
    };

    loadOptions();
  }, []);

  const handleChange = (field, value) => {
    setUserData((prev) => ({
      ...prev,
      [field]: value,
    }));
    setError(null);
    setSuccess(null);
  };

  const handleSave = async () => {
    if (!userData.id) {
      setError('User ID not found');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const token = await getValidToken();

      const updateData = {
        full_name: userData.full_name,
        bio: userData.bio || null,
        company_name: userData.company_name || null,
        school_name: userData.school_name || null,
        role_title: userData.role_title || null,
      };

      const response = await fetch(`${API_BASE}/api/users/${userData.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(updateData),
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setSuccess('Profile updated successfully!');
        if (data.data) {
          const updated = data.data;
          setUserData((prev) => ({
            ...prev,
            full_name: updated.full_name ?? prev.full_name,
            bio: updated.bio ?? '',
            company_name: updated.company_name ?? '',
            school_name: updated.school_name ?? '',
            role_title: updated.role_title ?? '',
          }));
        }
      } else {
        setError(data.detail || 'Failed to update profile');
      }
    } catch (err) {
      console.error('Error saving profile:', err);
      setError('Failed to save changes. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const getVerificationBadge = () => {
    switch (userData.verification_status) {
      case 'admin_verified':
        return <Badge color="green" leftSection={<IconShield size={12} />}>Admin Verified</Badge>;
      case 'email_verified':
        return <Badge color="blue" leftSection={<IconMail size={12} />}>Email Verified</Badge>;
      default:
        return <Badge color="gray">Unverified</Badge>;
    }
  };

  if (loading) {
    return (
      <Stack align="center" gap="md" py="xl" style={{ minHeight: '300px', justifyContent: 'center' }}>
        <Loader size="lg" />
        <Text>Loading your profile...</Text>
      </Stack>
    );
  }

  return (
    <Stack gap="xl">
      {/* Profile header card */}
      <Card mb="lg" style={{ background: 'linear-gradient(120deg, #e6fcf5 0%, #ffffff 100%)', border: '1px solid #e9ecef' }}>
        <Group gap="xl" align="center" wrap="wrap">
          <Avatar
            src={userData.profile_picture_url}
            size={80}
            radius="xl"
            color="teal"
          >
            {userData.full_name?.charAt(0)?.toUpperCase() || 'U'}
          </Avatar>
          <Stack gap={4} style={{ flex: 1 }}>
            <Title order={3} style={{ color: '#212529' }}>{userData.full_name || 'Your Profile'}</Title>
            <Text size="sm" c="dimmed">{userData.email}</Text>
            <Group gap="xs">
              {getVerificationBadge()}
            </Group>
          </Stack>
        </Group>
      </Card>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error">
          {error}
        </Alert>
      )}

      {success && (
        <Alert icon={<IconCheck size={16} />} color="green" title="Success">
          {success}
        </Alert>
      )}

      <Card withBorder padding="xl" radius="md">
        <Stack gap="lg">
          <Title order={3}>Profile Information</Title>

          <TextInput
            label="Email"
            value={userData.email}
            disabled
            leftSection={<IconMail size={16} />}
            description="Email cannot be changed"
          />

          <TextInput
            label="Full Name"
            placeholder="Your full name"
            value={userData.full_name}
            onChange={(e) => handleChange('full_name', e.target.value)}
            leftSection={<IconUser size={16} />}
            required
          />

          <Textarea
            label="Bio"
            placeholder="Tell others about yourself..."
            value={userData.bio}
            onChange={(e) => handleChange('bio', e.target.value)}
            minRows={3}
            maxRows={5}
          />

          <Divider label="Work & Education" labelPosition="center" />

          <Select
            label="Company"
            placeholder="Select company"
            data={companyOptions}
            searchable
            value={userData.company_name}
            onChange={(value) => handleChange('company_name', value || '')}
            leftSection={<IconBuilding size={16} />}
          />

          <Select
            label="School"
            placeholder="Select school"
            data={schoolOptions}
            searchable
            value={userData.school_name}
            onChange={(value) => handleChange('school_name', value || '')}
            leftSection={<IconSchool size={16} />}
          />

          <Select
            label="Job Title / Role"
            placeholder="Select role/title"
            data={roleTitleOptions}
            searchable
            value={userData.role_title}
            onChange={(value) => handleChange('role_title', value || '')}
            leftSection={<IconBriefcase size={16} />}
          />
        </Stack>
      </Card>

      <Group justify="flex-end">
        <Button
          size="lg"
          onClick={handleSave}
          loading={saving}
          color="teal"
          leftSection={<IconCheck size={18} />}
        >
          Save Changes
        </Button>
      </Group>
    </Stack>
  );
}
