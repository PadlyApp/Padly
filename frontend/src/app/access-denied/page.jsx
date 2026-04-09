'use client';

import { Container, Title, Text, Button, Stack, Center, ThemeIcon } from '@mantine/core';
import { IconShieldLock } from '@tabler/icons-react';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';

export default function AccessDeniedPage() {
  const router = useRouter();

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8f9fa' }}>
      <Navigation />
      <Container size="sm" style={{ padding: '6rem 2rem' }}>
        <Center>
          <Stack align="center" gap="lg">
            <ThemeIcon size={80} radius="xl" color="red" variant="light">
              <IconShieldLock size={40} />
            </ThemeIcon>
            <Title order={2} ta="center">Access Denied</Title>
            <Text c="dimmed" ta="center" size="lg" maw={400}>
              You don't have permission to view this page. This area is restricted to administrators.
            </Text>
            <Button
              variant="light"
              size="md"
              onClick={() => router.push('/')}
            >
              Go to Home
            </Button>
          </Stack>
        </Center>
      </Container>
    </div>
  );
}
