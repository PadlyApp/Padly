'use client';

import { Container, Title, Text, Button, Group, Paper, Loader, Center } from '@mantine/core';
import { useAuth } from './contexts/AuthContext';
import { useRouter } from 'next/navigation';

export default function Home() {
  const { user, logout, isLoading } = useAuth();
  const router = useRouter();

  if (isLoading) {
    return (
      <Center h="100vh">
        <Loader size="lg" />  
      </Center>
    );
  }

  if (!user) {
    // Not authenticated - show landing page
    return (
      <Container size="md" style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
        textAlign: 'center'
      }}>
        <Title order={1} size="h1" mb="md">
          Welcome to Padly
        </Title>
        <Text size="xl" c="dimmed" mb="xl">
          Your collaborative workspace is ready!
        </Text>
        
        <Group>
          <Button 
            size="lg" 
            onClick={() => router.push('/auth/login')}
          >
            Sign In
          </Button>
          <Button 
            size="lg" 
            variant="outline"
            onClick={() => router.push('/auth/signin')}
          >
            Create Account
          </Button>
        </Group>
      </Container>
    );
  }

  // Authenticated - show dashboard
  return (
    <Container size="md" py="xl">
      <Paper shadow="sm" p="xl" radius="md">
        <Title order={2} mb="md">
          Welcome back, {user.name}! 🎉
        </Title>
        <Text c="dimmed" mb="md">
          Email: {user.email}
        </Text>
        <Text c="dimmed" mb="xl">
          Member since: {new Date(user.createdAt).toLocaleDateString()}
        </Text>
        
        <Group>
          <Button onClick={logout} variant="outline" color="red">
            Logout
          </Button>
        </Group>
      </Paper>
    </Container>
  );
}

