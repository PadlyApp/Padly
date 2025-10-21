'use client';

import Link from 'next/link';
import { 
  Container, 
  Title, 
  Text, 
  Button, 
  Group, 
  Stack,
  Loader,
  Flex,
  Box
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useAuth } from './contexts/AuthContext';

export default function Home() {
  const { user, isAuthenticated, signout, isLoading } = useAuth();

  const handleLogout = async () => {
    try {
      await signout();
      notifications.show({
        title: 'Signed out',
        message: 'You have been successfully signed out',
        color: 'blue',
      });
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to sign out',
        color: 'red',
      });
    }
  };

  if (isLoading) {
    return (
      <Container size="md" style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
      }}>
        <Loader size="lg" />
        <Text mt="md">Loading...</Text>
      </Container>
    );
  }

  return (
    <Box style={{ minHeight: '100vh' }}>
      {/* Header with auth buttons */}
      <Box 
        style={{
          position: 'absolute',
          top: '1rem',
          right: '1rem',
          zIndex: 100
        }}
      >
        {isAuthenticated ? (
          <Group>
            <Text size="sm" c="dimmed">
              Welcome, {user?.profile?.full_name || user?.email}!
            </Text>
            <Button 
              variant="light" 
              color="red" 
              size="sm"
              onClick={handleLogout}
            >
              Logout
            </Button>
          </Group>
        ) : (
          <Group>
            <Button 
              component={Link} 
              href="/login" 
              variant="light"
              size="sm"
            >
              Login
            </Button>
            <Button 
              component={Link} 
              href="/signup" 
              size="sm"
            >
              Sign Up
            </Button>
          </Group>
        )}
      </Box>

      {/* Main content */}
      <Container size="md" style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
        textAlign: 'center'
      }}>
        <Stack align="center" gap="xl">
          <Title 
            order={1} 
            size="h1" 
            fw={900}
            style={{ fontSize: '3rem' }}
          >
            Welcome to Padly
          </Title>
          
          <Text size="xl" c="dimmed" maw={500}>
            {isAuthenticated 
              ? 'Your collaborative workspace is ready!' 
              : 'Please sign in to access your collaborative workspace.'
            }
          </Text>

          {!isAuthenticated && (
            <Group mt="xl">
              <Button 
                component={Link} 
                href="/login" 
                size="lg"
                variant="light"
              >
                Get Started - Login
              </Button>
              <Button 
                component={Link} 
                href="/signup" 
                size="lg"
              >
                Create Account
              </Button>
            </Group>
          )}
        </Stack>
      </Container>
    </Box>
  );
}

