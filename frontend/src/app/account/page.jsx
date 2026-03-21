'use client';

import { useState, useEffect } from 'react';
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
  Badge
} from '@mantine/core';
import { 
  IconUser, 
  IconBuilding, 
  IconSchool, 
  IconBriefcase, 
  IconCheck, 
  IconAlertCircle,
  IconMail,
  IconShield
} from '@tabler/icons-react';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { useAuth } from '../contexts/AuthContext';

export default function AccountPage() {
  return (
    <ProtectedRoute>
      <AccountPageContent />
    </ProtectedRoute>
  );
}

function AccountPageContent() {
  const { authState, getValidToken } = useAuth();
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [companyOptions, setCompanyOptions] = useState([]);
  const [schoolOptions, setSchoolOptions] = useState([]);
  const [roleTitleOptions, setRoleTitleOptions] = useState([]);
  
  // User profile data
  const [userData, setUserData] = useState({
    id: '',
    email: '',
    full_name: '',
    bio: '',
    company_name: '',
    school_name: '',
    role_title: '',
    verification_status: 'unverified',
    profile_picture_url: ''
  });

  // Fetch user data on mount
  useEffect(() => {
    const fetchUserData = async () => {
      if (!authState?.accessToken) return;
      
      try {
        const token = await getValidToken();
        const response = await fetch('http://localhost:8000/api/auth/me', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        const data = await response.json();
        
        if (response.ok && data.user) {
          // Profile data is in data.user.profile, email is in data.user.email
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
            profile_picture_url: profile.profile_picture_url ?? ''
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
          fetch('http://localhost:8000/api/options/companies?limit=500'),
          fetch('http://localhost:8000/api/options/schools?limit=500'),
          fetch('http://localhost:8000/api/options/roles'),
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

  // Handle form field changes
  const handleChange = (field, value) => {
    setUserData(prev => ({
      ...prev,
      [field]: value
    }));
    // Clear messages when user starts editing
    setError(null);
    setSuccess(null);
  };

  // Save changes
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
      
      // Prepare update data (only send editable fields)
      const updateData = {
        full_name: userData.full_name,
        bio: userData.bio || null,
        company_name: userData.company_name || null,
        school_name: userData.school_name || null,
        role_title: userData.role_title || null
      };
      
      const response = await fetch(`http://localhost:8000/api/users/${userData.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(updateData)
      });
      
      const data = await response.json();
      
      if (response.ok && data.status === 'success') {
        setSuccess('Profile updated successfully!');
        // Update local state with response data (ensure no nulls)
        if (data.data) {
          const updated = data.data;
          setUserData(prev => ({
            ...prev,
            full_name: updated.full_name ?? prev.full_name,
            bio: updated.bio ?? '',
            company_name: updated.company_name ?? '',
            school_name: updated.school_name ?? '',
            role_title: updated.role_title ?? ''
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
      <Box style={{ minHeight: '100vh', backgroundColor: '#fafafa' }}>
        <Navigation />
        <Container size="md" py="xl">
          <Stack align="center" gap="md" style={{ minHeight: '400px', justifyContent: 'center' }}>
            <Loader size="lg" />
            <Text>Loading your account...</Text>
          </Stack>
        </Container>
      </Box>
    );
  }

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#fafafa' }}>
      <Navigation />
      
      <Container size="md" py="xl">
        <Stack gap="xl">
          {/* Header */}
          <Stack align="center" gap="md">
            <Avatar 
              src={userData.profile_picture_url} 
              size={100} 
              radius="50%"
              color="blue"
            >
              {userData.full_name?.charAt(0)?.toUpperCase() || 'U'}
            </Avatar>
            <Title order={1}>Your Account</Title>
            <Group gap="xs">
              {getVerificationBadge()}
            </Group>
          </Stack>

          {/* Messages */}
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

          {/* Profile Card */}
          <Card withBorder padding="xl" radius="md">
            <Stack gap="lg">
              <Title order={3}>Profile Information</Title>
              
              {/* Email (read-only) */}
              <TextInput
                label="Email"
                value={userData.email}
                disabled
                leftSection={<IconMail size={16} />}
                description="Email cannot be changed"
              />
              
              {/* Full Name */}
              <TextInput
                label="Full Name"
                placeholder="Your full name"
                value={userData.full_name}
                onChange={(e) => handleChange('full_name', e.target.value)}
                leftSection={<IconUser size={16} />}
                required
              />
              
              {/* Bio */}
              <Textarea
                label="Bio"
                placeholder="Tell others about yourself..."
                value={userData.bio}
                onChange={(e) => handleChange('bio', e.target.value)}
                minRows={3}
                maxRows={5}
              />
              
              <Divider label="Work & Education" labelPosition="center" />
              
              {/* Company */}
              <Select
                label="Company"
                placeholder="Select company"
                data={companyOptions}
                searchable
                value={userData.company_name}
                onChange={(value) => handleChange('company_name', value || '')}
                leftSection={<IconBuilding size={16} />}
              />
              
              {/* School */}
              <Select
                label="School"
                placeholder="Select school"
                data={schoolOptions}
                searchable
                value={userData.school_name}
                onChange={(value) => handleChange('school_name', value || '')}
                leftSection={<IconSchool size={16} />}
              />
              
              {/* Role/Title */}
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

          {/* Save Button */}
          <Group justify="center">
            <Button 
              size="lg" 
              onClick={handleSave}
              loading={saving}
              leftSection={<IconCheck size={18} />}
            >
              Save Changes
            </Button>
          </Group>
        </Stack>
      </Container>
    </Box>
  );
}
