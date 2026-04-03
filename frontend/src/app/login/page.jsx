'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Alert,
  TextInput,
  PasswordInput,
  Button,
  Title,
  Text,
  Stack,
  Box,
  Group,
} from '@mantine/core';
import { IconHome, IconCheck, IconAlertCircle } from '@tabler/icons-react';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../contexts/AuthContext';
import { normalizeAuthErrorMessage } from '../../../lib/errorHandling';

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const { signin } = useAuth();
  const router = useRouter();

  const form = useForm({
    initialValues: {
      email: '',
      password: '',
    },
    validate: {
      email: (value) => (/^\S+@\S+$/.test(value) ? null : 'Invalid email'),
      password: (value) => (!value ? 'Password is required' : null),
    },
  });

  useEffect(() => {
    if (submitError) setSubmitError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.values.email, form.values.password]);

  const emailInputProps = form.getInputProps('email');
  const passwordInputProps = form.getInputProps('password');

  const handleSubmit = async (values) => {
    setIsLoading(true);
    setSubmitError(null);

    try {
      await signin(values.email, values.password);
      notifications.show({
        title: 'Welcome back!',
        message: 'Successfully signed in',
        color: 'green',
      });

      // Check if user has completed onboarding
      const onboardingComplete = localStorage.getItem('padly_onboarding_complete');
      if (!onboardingComplete) {
        router.push('/onboarding');
      } else {
        router.push('/');
      }
    } catch (err) {
      const message = normalizeAuthErrorMessage(err, { flow: 'signin' });
      setSubmitError(message);
      notifications.show({
        title: 'Sign-in failed',
        message,
        color: 'red',
      });
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
            Find your perfect place
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
            <Title order={2} style={{ color: '#212529' }}>Welcome back</Title>
            <Text size="sm" c="dimmed">
              Don't have an account?{' '}
              <Link href="/signup" style={{ color: '#20c997', fontWeight: 500 }}>
                Sign up free
              </Link>
            </Text>
          </Stack>

          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack>
              {submitError && (
                <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />}>
                  {submitError}
                </Alert>
              )}

              <TextInput
                label="Email"
                placeholder="your@email.com"
                required
                {...emailInputProps}
                onChange={(event) => {
                  setSubmitError(null);
                  emailInputProps.onChange(event);
                }}
              />

              <PasswordInput
                label="Password"
                placeholder="Your password"
                required
                {...passwordInputProps}
                onChange={(event) => {
                  setSubmitError(null);
                  passwordInputProps.onChange(event);
                }}
              />

              <Button
                type="submit"
                fullWidth
                loading={isLoading}
                mt="md"
                color="teal"
                size="md"
              >
                Sign In
              </Button>
            </Stack>
          </form>
        </Stack>
      </Box>
    </Box>
  );
}
