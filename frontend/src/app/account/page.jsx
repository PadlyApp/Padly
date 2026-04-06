'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

import { useState, useEffect, useLayoutEffect, useRef, Suspense } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
  Grid,
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
  IconHeart,
  IconCheck,
  IconAlertCircle,
  IconMail,
  IconShield,
  IconSettings,
  IconMapPin,
} from '@tabler/icons-react';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { PreferencesForm } from '../components/PreferencesForm';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { SkeletonAccountProfile, SkeletonListingCard } from '../components/Skeletons';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../../../lib/api';

function AccountTabs() {
  const searchParams = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const initialTab = tabFromUrl === 'preferences'
    ? 'preferences'
    : tabFromUrl === 'interested'
      ? 'interested'
      : 'profile';
  const [activeTab, setActiveTab] = useState(initialTab);

  useEffect(() => {
    const t = searchParams.get('tab');
    if (t === 'preferences') setActiveTab('preferences');
    else if (t === 'interested') setActiveTab('interested');
    else setActiveTab('profile');
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
        <Tabs.Tab value="interested" leftSection={<IconHeart size={16} />}>
          Interested Listings
        </Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="profile">
        <ProfilePanel />
      </Tabs.Panel>

      <Tabs.Panel value="preferences">
        <PreferencesForm />
      </Tabs.Panel>

      <Tabs.Panel value="interested">
        <InterestedListingsPanel />
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
  const queryClient = useQueryClient();
  const prevMeRef = useRef(null);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

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

  // ── Cached profile fetch ──────────────────────────────────────────────────

  const { data: meData, isLoading: meLoading } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const token = await getValidToken();
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return res.json();
    },
    enabled: !!authState?.accessToken,
    staleTime: 5 * 60 * 1000,
    gcTime:    10 * 60 * 1000,
  });

  // Sync query result → controlled form state once per new fetch
  useLayoutEffect(() => {
    if (!meData || meData === prevMeRef.current) return;
    prevMeRef.current = meData;
    if (meData.user) {
      const profile = meData.user.profile || {};
      setUserData({
        id: profile.id ?? '',
        email: meData.user.email ?? profile.email ?? '',
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
  }, [meData]);

  const loading = meLoading && !meData;

  // ── Cached dropdown options (static data; 30-min stale time) ─────────────

  const { data: options } = useQuery({
    queryKey: ['profile-options'],
    queryFn: async () => {
      const [c, s, r] = await Promise.all([
        fetch(`${API_BASE}/api/options/companies?limit=500`).then((res) => res.json()),
        fetch(`${API_BASE}/api/options/schools?limit=500`).then((res) => res.json()),
        fetch(`${API_BASE}/api/options/roles`).then((res) => res.json()),
      ]);
      return {
        companies: c.data || [],
        schools:   s.data || [],
        roles:     r.data || [],
      };
    },
    staleTime: 30 * 60 * 1000,
    gcTime:    60 * 60 * 1000,
  });

  const companyOptions    = options?.companies ?? [];
  const schoolOptions     = options?.schools   ?? [];
  const roleTitleOptions  = options?.roles     ?? [];

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
        queryClient.invalidateQueries({ queryKey: ['me'] });
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
    return <SkeletonAccountProfile />;
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

function InterestedListingsPanel() {
  const { authState, getValidToken } = useAuth();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['interested-listings'],
    queryFn: async () => {
      const token = await getValidToken();
      return api.getInterestedListings(token);
    },
    enabled: !!authState?.accessToken,
    staleTime: 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  const listings = data?.data || [];

  const handleRemove = async (listingId) => {
    const token = await getValidToken();
    await api.unmarkInterestedListing(token, listingId);
    await queryClient.invalidateQueries({ queryKey: ['interested-listings'] });
  };

  if (isLoading) {
    return (
      <Grid gutter="lg">
        {Array.from({ length: 3 }).map((_, index) => (
          <Grid.Col key={index} span={{ base: 12, md: 6, xl: 4 }}>
            <SkeletonListingCard />
          </Grid.Col>
        ))}
      </Grid>
    );
  }

  if (error) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="red" title="Unable to load interested listings">
        {getErrorMessage(error, 'Please try again in a moment.')}
      </Alert>
    );
  }

  if (listings.length === 0) {
    return (
      <Card withBorder padding="xl" radius="md">
        <Stack gap="xs" align="center" py="xl">
          <IconHeart size={32} color="#12b886" />
          <Title order={3}>No interested listings yet</Title>
          <Text c="dimmed" ta="center" maw={420}>
            When you open a listing and tap &quot;I&apos;m interested&quot;, it will show up here.
          </Text>
        </Stack>
      </Card>
    );
  }

  return (
    <Stack gap="lg">
      <Text c="dimmed">
        {listings.length} interested listing{listings.length === 1 ? '' : 's'}
      </Text>

      <Grid gutter="lg">
        {listings.map((listing) => {
          const image = (() => {
            if (Array.isArray(listing.images)) return listing.images[0];
            if (typeof listing.images === 'string') {
              try {
                const parsed = JSON.parse(listing.images);
                if (Array.isArray(parsed)) return parsed[0];
              } catch {
                return listing.images;
              }
            }
            return 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080';
          })();

          const title = listing.title || 'Listing';
          const location = [listing.city, listing.state].filter(Boolean).join(', ');

          return (
            <Grid.Col key={listing.id || listing.listing_id} span={{ base: 12, md: 6, xl: 4 }}>
              <Card withBorder radius="lg" padding="md" style={{ height: '100%' }}>
                <Card.Section>
                  <Box style={{ position: 'relative', paddingBottom: '62%', backgroundColor: '#f3f4f6' }}>
                    <ImageWithFallback
                      src={image}
                      alt={title}
                      style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                      }}
                    />
                  </Box>
                </Card.Section>

                <Stack gap="sm" mt="md">
                  <Stack gap={4}>
                    <Text fw={600} lineClamp={2}>
                      {title}
                    </Text>
                    {location && (
                      <Group gap={4}>
                        <IconMapPin size={13} color="#868e96" />
                        <Text size="sm" c="dimmed" lineClamp={1}>
                          {location}
                        </Text>
                      </Group>
                    )}
                  </Stack>

                  {listing.price_per_month != null && (
                    <Text fw={700} size="lg" c="teal.6">
                      ${Number(listing.price_per_month).toLocaleString()}/mo
                    </Text>
                  )}

                  <Text size="sm" c="dimmed">
                    {[
                      listing.number_of_bedrooms != null && (listing.number_of_bedrooms === 0 ? 'Studio' : `${listing.number_of_bedrooms} Bed`),
                      listing.number_of_bathrooms != null && `${listing.number_of_bathrooms} Bath`,
                      listing.area_sqft != null && `${Number(listing.area_sqft).toLocaleString()} sq ft`,
                    ].filter(Boolean).join(' · ')}
                  </Text>

                  <Group grow mt="sm">
                    <Button
                      component="a"
                      href={`/listings/${listing.id}`}
                      color="teal"
                      variant="light"
                    >
                      View Details
                    </Button>
                    <Button
                      color="gray"
                      variant="subtle"
                      onClick={() => handleRemove(String(listing.id))}
                    >
                      Remove
                    </Button>
                  </Group>
                </Stack>
              </Card>
            </Grid.Col>
          );
        })}
      </Grid>
    </Stack>
  );
}
