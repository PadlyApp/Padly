'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  TextInput,
  PasswordInput,
  Button,
  Title,
  Text,
  Stack,
  Box,
  Group,
} from '@mantine/core';
import { IconHome, IconCheck } from '@tabler/icons-react';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../contexts/AuthContext';

export default function SignupPage() {
  const [isLoading, setIsLoading] = useState(false);
  const { signup } = useAuth();
  const router = useRouter();

  const form = useForm({
    initialValues: {
      fullName: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
    validate: {
      fullName: (value) => (!value ? 'Full name is required' : null),
      email: (value) => (/^\S+@\S+$/.test(value) ? null : 'Invalid email'),
      password: (value) =>
        value.length < 6 ? 'Password must be at least 6 characters long' : null,
      confirmPassword: (value, values) =>
        value !== values.password ? 'Passwords do not match' : null,
    },
  });

  const handleSubmit = async (values) => {
    setIsLoading(true);

    try {
      await signup(values.email, values.password, values.fullName);
      notifications.show({
        title: 'Success!',
        message: 'Account created successfully',
        color: 'green',
      });
      // Redirect to onboarding to complete profile
      router.push('/onboarding');
    } catch (err) {
      // Check if it's an email confirmation message
      if (err.message && err.message.includes('check your email')) {
        notifications.show({
          title: 'Account Created!',
          message: err.message,
          color: 'blue',
          autoClose: 8000,
        });
        // Redirect to login page
        router.push('/login');
      } else {
        notifications.show({
          title: 'Registration Failed',
          message: err.message || 'Failed to create account. Please try again.',
          color: 'red',
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box className="auth-split">
      {/* Left brand panel — desktop only */}
      <Box
        visibleFrom="md"
        style={{
          background: 'linear-gradient(160deg, #087f5b 0%, #20c997 100%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '3rem',
          minHeight: '100vh',
        }}
      >
        <Stack gap="xl" align="center" style={{ maxWidth: 360, textAlign: 'center' }}>
          <Group gap="xs" justify="center">
            <Box style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <IconHome size={20} color="white" />
            </Box>
            <Text size="xl" fw={700} style={{ color: 'white', letterSpacing: '-0.01em' }}>Padly</Text>
          </Group>
          <Title order={2} style={{ color: 'white', lineHeight: 1.2 }}>
            Your compatible roommate is already here.
          </Title>
          <Text style={{ color: 'rgba(255,255,255,0.8)', lineHeight: 1.65 }}>
            AI-powered housing discovery built for students and early-career professionals.
          </Text>
          <Stack gap="sm" align="flex-start" style={{ width: '100%' }}>
            {['Smart matching based on your lifestyle', 'Find compatible roommates easily', 'Verified listings, no scams'].map((point) => (
              <Group key={point} gap="sm">
                <Box style={{ width: 20, height: 20, borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <IconCheck size={12} color="white" />
                </Box>
                <Text size="sm" style={{ color: 'rgba(255,255,255,0.9)' }}>{point}</Text>
              </Group>
            ))}
          </Stack>
        </Stack>
      </Box>

      {/* Right form panel */}
      <Box style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        backgroundColor: '#ffffff',
        minHeight: '100vh',
      }}>
        <Stack gap="xl" style={{ width: '100%', maxWidth: 400 }}>
          {/* Logo shown on mobile only */}
          <Group gap="xs" hiddenFrom="md">
            <Box style={{ width: 28, height: 28, borderRadius: 8, background: '#20c997', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <IconHome size={16} color="white" />
            </Box>
            <Text size="lg" fw={700} style={{ color: '#212529' }}>Padly</Text>
          </Group>

          <Stack gap="xs">
            <Title order={2} style={{ color: '#212529' }}>Create your account</Title>
            <Text size="sm" c="dimmed">
              Already have an account?{' '}
              <Link href="/login" style={{ color: '#20c997', fontWeight: 500 }}>
                Sign in
              </Link>
            </Text>
          </Stack>

          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack>
              <TextInput
                label="Full Name"
                placeholder="Your full name"
                required
                {...form.getInputProps('fullName')}
              />

              <TextInput
                label="Email"
                placeholder="your@email.com"
                required
                {...form.getInputProps('email')}
              />

              <PasswordInput
                label="Password"
                placeholder="Your password"
                required
                {...form.getInputProps('password')}
              />

              <PasswordInput
                label="Confirm Password"
                placeholder="Confirm your password"
                required
                {...form.getInputProps('confirmPassword')}
              />

              <Button
                type="submit"
                fullWidth
                loading={isLoading}
                mt="md"
                color="teal"
                size="md"
              >
                Create Free Account
              </Button>
            </Stack>
          </form>
        </Stack>
      </Box>
    </Box>
  );
}
