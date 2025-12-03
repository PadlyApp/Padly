'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  TextInput, 
  PasswordInput, 
  Button, 
  Paper, 
  Title, 
  Text, 
  Container, 
  Stack,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
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

  const handleSubmit = async (values) => {
    console.log("clicked - attempting signin with:", values.email);
    setIsLoading(true);

    try {
      console.log("Calling signin...");
      await signin(values.email, values.password);
      console.log("Signin successful!");
      notifications.show({
        title: 'Welcome back!',
        message: 'Successfully signed in',
        color: 'green',
      });
      
      // Check if user has completed onboarding
      const onboardingComplete = localStorage.getItem('padly_onboarding_complete');
      if (!onboardingComplete) {
        // Redirect to onboarding if not completed
        router.push('/onboarding');
      } else {
        router.push('/');
      }
    } catch (err) {
      console.error("Signin error:", err);
      notifications.show({
        title: 'Login Failed',
        message: err.message || 'Invalid credentials. Please try again.',
        color: 'red',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container size={420} my={40}>
      <Title ta="center" fw={900}>
        Welcome back to Padly
      </Title>
      <Text c="dimmed" size="sm" ta="center" mt={5}>
        Don't have an account yet?{' '}
        <Link href="/signup" style={{ color: 'var(--mantine-color-blue-filled)' }}>
          Create account
        </Link>
      </Text>

      <Paper withBorder shadow="md" p={30} mt={30} radius="md">
        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack>
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

            <Button 
              type="submit" 
              fullWidth 
              loading={isLoading}
              mt="md"
            >
              Sign In
            </Button>
          </Stack>
        </form>
      </Paper>
    </Container>
  );
}

