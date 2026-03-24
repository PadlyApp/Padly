'use client';

import { useEffect } from 'react';
import { Container, Title, Text, Button, Stack, Box, Group } from '@mantine/core';
import Link from 'next/link';
import { Navigation } from './components/Navigation';
import { useAuth } from './contexts/AuthContext';
import { usePadlyTour } from './contexts/TourContext';

export default function Home() {
  const { isAuthenticated, isLoading } = useAuth();
  const { tourPhase, isTourActive, isReady: tourReady, startTour } = usePadlyTour();

  useEffect(() => {
    if (!tourReady || isLoading || !isAuthenticated) return;

    const onboardingDone = localStorage.getItem('padly_onboarding_complete') === 'true';
    let tourDone = false;
    try {
      const tourState = localStorage.getItem('padly_tour_state');
      tourDone = tourState && JSON.parse(tourState).phase === 'complete';
    } catch {
      // corrupt state — treat as not done
    }

    if (onboardingDone && !tourDone && !isTourActive) {
      startTour();
    }
  }, [tourReady, isLoading, isAuthenticated, isTourActive, startTour]);

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />
      
      <Container size="md" style={{ padding: '6rem 2rem' }}>
        <Stack align="center" gap="xl">
          {/* Hero Section */}
          <Stack align="center" gap="lg" style={{ textAlign: 'center' }}>
            <Title 
              order={1} 
              style={{ 
                fontSize: '3.5rem', 
                fontWeight: 600,
                color: '#111',
                lineHeight: 1.2
              }}
            >
              Welcome to Padly
            </Title>
            <Text 
              size="xl" 
              c="dimmed" 
              style={{ 
                maxWidth: '42rem',
                color: '#666',
                fontSize: '1.25rem'
              }}
            >
              A trusted platform for students, interns, and early-career professionals to find housing and compatible roommates.
            </Text>
          </Stack>

          {/* CTA Buttons - Show different buttons based on auth state */}
          {!isLoading && (
            <Group gap="lg" mt="xl">
              {isAuthenticated ? (
                // Authenticated users see View Matches and Set Preferences
                <>
                  <Link href="/matches" style={{ textDecoration: 'none' }}>
                    <Button
                      size="lg"
                      radius="md"
                      style={{
                        backgroundColor: '#20c997',
                        padding: '0.75rem 2rem',
                        fontSize: '1.125rem',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#12b886';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#20c997';
                      }}
                    >
                      View Matches
                    </Button>
                  </Link>
                  <Link href="/account?tab=preferences" style={{ textDecoration: 'none' }}>
                    <Button
                      size="lg"
                      radius="md"
                      variant="outline"
                      color="gray"
                      style={{
                        padding: '0.75rem 2rem',
                        fontSize: '1.125rem',
                        borderColor: '#ddd',
                        color: '#666',
                      }}
                    >
                      Set Preferences
                    </Button>
                  </Link>
                </>
              ) : (
                // Unauthenticated users see Login and Sign Up
                <>
                  <Link href="/login" style={{ textDecoration: 'none' }}>
                    <Button
                      size="lg"
                      radius="md"
                      variant="outline"
                      color="gray"
                      style={{
                        padding: '0.75rem 2rem',
                        fontSize: '1.125rem',
                        borderColor: '#ddd',
                        color: '#666',
                      }}
                    >
                      Log In
                    </Button>
                  </Link>
                  <Link href="/signup" style={{ textDecoration: 'none' }}>
                    <Button
                      size="lg"
                      radius="md"
                      style={{
                        backgroundColor: '#20c997',
                        padding: '0.75rem 2rem',
                        fontSize: '1.125rem',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#12b886';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#20c997';
                      }}
                    >
                      Sign Up
                    </Button>
                  </Link>
                </>
              )}
            </Group>
          )}

          {/* Feature Highlights */}
          <Stack gap="xl" mt={80} style={{ width: '100%', maxWidth: '48rem' }}>
            <Title order={2} ta="center" style={{ color: '#111', fontSize: '2rem' }}>
              Why Choose Padly?
            </Title>
            
            <Stack gap="lg">
              <Box style={{ padding: '1.5rem', borderRadius: '0.75rem', border: '1px solid #f1f1f1' }}>
                <Title order={3} size="h4" mb="sm" style={{ color: '#111' }}>
                  🏠 Verified Listings
                </Title>
                <Text c="dimmed" style={{ color: '#666' }}>
                  All listings are verified and posted by trusted hosts and students.
                </Text>
              </Box>

              <Box style={{ padding: '1.5rem', borderRadius: '0.75rem', border: '1px solid #f1f1f1' }}>
                <Title order={3} size="h4" mb="sm" style={{ color: '#111' }}>
                  🤝 Compatible Roommates
                </Title>
                <Text c="dimmed" style={{ color: '#666' }}>
                  Find roommates who match your lifestyle preferences and professional goals.
                </Text>
              </Box>

              <Box style={{ padding: '1.5rem', borderRadius: '0.75rem', border: '1px solid #f1f1f1' }}>
                <Title order={3} size="h4" mb="sm" style={{ color: '#111' }}>
                  🔒 Secure Platform
                </Title>
                <Text c="dimmed" style={{ color: '#666' }}>
                  Built with security in mind, protecting your data and communications.
                </Text>
              </Box>
            </Stack>
          </Stack>
        </Stack>
      </Container>
    </Box>
  );
}

