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
  Alert,
  Stack,
  Group
} from '@mantine/core';
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
      router.push('/');
    } catch (err) {
      // Check if it's an email confirmation message
      if (err.message && err.message.includes('check your email')) {
        notifications.show({
          title: 'Account Created!',
          message: err.message,
          color: 'blue',
          autoClose: 8000, // Keep longer since it's important info
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
    <Container size={420} my={40}>
      <Title ta="center" fw={900}>
        Join Padly
      </Title>
      <Text c="dimmed" size="sm" ta="center" mt={5}>
        Already have an account?{' '}
        <Link href="/login" style={{ color: 'var(--mantine-color-blue-filled)' }}>
          Sign in
        </Link>
      </Text>

      <Paper withBorder shadow="md" p={30} mt={30} radius="md">
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
            >
              Create Account
            </Button>
          </Stack>
        </form>
      </Paper>
    </Container>
  );
}

