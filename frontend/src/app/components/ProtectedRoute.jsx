'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../contexts/AuthContext';
import { Container, Loader, Center } from '@mantine/core';

export function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <Container>
        <Center style={{ minHeight: '100vh' }}>
          <Loader size="lg" />
        </Center>
      </Container>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

