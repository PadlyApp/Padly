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
  Divider,
} from '@mantine/core';
import { IconHome, IconCheck, IconAlertCircle } from '@tabler/icons-react';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../contexts/AuthContext';
import { normalizeAuthErrorMessage } from '../../../lib/errorHandling';

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 6.293C4.672 4.166 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  );
}

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const { signin, signInWithGoogle } = useAuth();
  const router = useRouter();

  const handleGoogleSignIn = async () => {
    setIsGoogleLoading(true);
    setSubmitError(null);
    try {
      await signInWithGoogle();
      // Page redirects to Google — no further action needed here
    } catch (err) {
      setSubmitError('Could not start Google sign-in. Please try again.');
      setIsGoogleLoading(false);
    }
  };

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
      const authResponse = await signin(values.email, values.password);
      notifications.show({
        title: 'Welcome back!',
        message: 'Successfully signed in',
        color: 'green',
      });

      // Ask /me for server-side truth on whether preferences are set.
      // The /signin response doesn't include has_preferences, so we fetch it here.
      let hasPreferences = false;
      try {
        const token = authResponse?.access_token;
        if (token) {
          const { AuthService } = await import('../../../lib/authService');
          const meData = await AuthService.getCurrentUser(token);
          hasPreferences = meData?.user?.has_preferences ?? false;
        }
      } catch {
        hasPreferences = !!localStorage.getItem('padly_preferences_complete');
      }

      router.push(hasPreferences ? '/discover' : '/preferences-setup');
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

          <Stack gap="sm">
            <Button
              fullWidth
              variant="default"
              size="md"
              leftSection={<GoogleIcon />}
              loading={isGoogleLoading}
              onClick={handleGoogleSignIn}
            >
              Continue with Google
            </Button>
          </Stack>

          <Divider label="or" labelPosition="center" />

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
