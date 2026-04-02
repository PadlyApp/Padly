'use client';

import {
  TextInput,
  PasswordInput,
  Anchor,
  Paper,
  Title,
  Text,
  Container,
  Button,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../contexts/AuthContext';

interface SigninFormValues {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export default function SigninPage() {
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { signup } = useAuth();

  const form = useForm<SigninFormValues>({
    initialValues: {
      name: '',
      email: '',
      password: '',
      confirmPassword: '',
    },

    validate: {
      name: (val) => (val.length < 2 ? 'Name should have at least 2 characters' : null),
      email: (val) => (/^\S+@\S+$/.test(val) ? null : 'Invalid email'),
      password: (val) => (val.length < 6 ? 'Password should include at least 6 characters' : null),
      confirmPassword: (val, values) => 
        val !== values.password ? 'Passwords do not match' : null,
    },
  });

  const handleSubmit = async (values: SigninFormValues) => {
    setLoading(true);
    
    try {
      await signup(values.email, values.password, values.name);

      notifications.show({
        title: 'Account Created',
        message: `Welcome to Padly, ${values.name}!`,
        color: 'green',
      });

      router.push('/');

    } catch (error) {
      notifications.show({
        title: 'Registration Failed',
        message: error instanceof Error ? error.message : 'Something went wrong',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container size={420} my={40}>
      <Title ta="center" style={{ fontWeight: 900 }}>
        Join Padly today
      </Title>
      <Text c="dimmed" size="sm" ta="center" mt={5}>
        Already have an account?{' '}
        <Anchor size="sm" component="button" onClick={() => router.push('/auth/login')}>
          Sign in
        </Anchor>
      </Text>

      <Paper withBorder shadow="md" p={30} mt={30} radius="md">
        <form onSubmit={form.onSubmit(handleSubmit)}>
          <TextInput
            label="Full Name"
            placeholder="Your name"
            required
            {...form.getInputProps('name')}
          />
          <TextInput
            label="Email"
            placeholder="hello@padly.com"
            required
            mt="md"
            {...form.getInputProps('email')}
          />
          <PasswordInput
            label="Password"
            placeholder="Your password"
            required
            mt="md"
            {...form.getInputProps('password')}
          />
          <PasswordInput
            label="Confirm Password"
            placeholder="Confirm your password"
            required
            mt="md"
            {...form.getInputProps('confirmPassword')}
          />
          <Button 
            type="submit" 
            fullWidth 
            mt="xl"
            loading={loading}
          >
            Create account
          </Button>
        </form>
      </Paper>
    </Container>
  );
}