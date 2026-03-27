'use client';

import { useEffect } from 'react';
import { Box, Container, Grid, Stack, Group, Title, Text, Badge, Button, Card, ActionIcon } from '@mantine/core';
import { IconHome, IconHeart, IconX, IconUsers, IconShieldCheck, IconSparkles, IconUser, IconSettings } from '@tabler/icons-react';
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
    <Box>
      <Navigation />

      {/* ── SECTION 1: HERO ──────────────────────────────────── */}
      <Box className="hero-gradient" style={{ paddingTop: '5rem', paddingBottom: '5rem' }}>
        {/* Liquid blobs */}
        <div className="hero-blob hero-blob-1" />
        <div className="hero-blob hero-blob-2" />
        <div className="hero-blob hero-blob-3" />
        <div className="hero-blob hero-blob-4" />
        <Container size="xl" style={{ position: 'relative', zIndex: 1 }}>
          <Grid align="center" gutter={{ base: 'xl', md: 60 }}>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Stack gap="xl">
                <Badge variant="light" color="teal" size="lg" radius="xl" style={{ width: 'fit-content' }}>
                  Housing. Matched.
                </Badge>
                <Title order={1} style={{ fontSize: 'clamp(2.2rem, 5vw, 3.25rem)', lineHeight: 1.1, color: '#212529' }}>
                  Your next place,<br />matched to you.
                </Title>
                <Text size="lg" style={{ color: '#868e96', maxWidth: '36rem', lineHeight: 1.65 }}>
                  AI-powered housing discovery for students and early-career professionals.
                  Swipe through listings, find compatible roommates, and move in faster.
                </Text>

                {!isLoading && (
                  isAuthenticated ? (
                    <Group gap="md">
                      <Button size="lg" color="teal" component={Link} href="/discover">
                        Continue Discovering
                      </Button>
                      <Button size="lg" variant="outline" color="teal" component={Link} href="/groups">
                        My Groups
                      </Button>
                    </Group>
                  ) : (
                    <Group gap="md">
                      <Button size="lg" color="teal" component={Link} href="/signup">
                        Find Your Place
                      </Button>
                      <Button size="lg" variant="outline" color="teal" component={Link} href="/discover">
                        Browse Listings
                      </Button>
                    </Group>
                  )
                )}

                <Group gap="xl">
                  <Stack gap={2}>
                    <Text fw={700} size="xl" style={{ color: '#212529' }}>1,200+</Text>
                    <Text size="sm" c="dimmed">Active listings</Text>
                  </Stack>
                  <Stack gap={2}>
                    <Text fw={700} size="xl" style={{ color: '#212529' }}>500+</Text>
                    <Text size="sm" c="dimmed">Matches made</Text>
                  </Stack>
                  <Stack gap={2}>
                    <Text fw={700} size="xl" style={{ color: '#212529' }}>50+</Text>
                    <Text size="sm" c="dimmed">Cities covered</Text>
                  </Stack>
                </Group>
              </Stack>
            </Grid.Col>

            <Grid.Col span={{ base: 12, md: 6 }}>
              {/* Mock swipe card — decorative */}
              <Box style={{ position: 'relative', maxWidth: 340, margin: '0 auto' }}>
                {/* Background stacked cards */}
                <Box style={{
                  position: 'absolute', top: 16, left: 16, right: -16,
                  height: 420, borderRadius: 20,
                  background: 'rgba(32,201,151,0.08)',
                  border: '1px solid rgba(32,201,151,0.2)',
                }} />
                <Box style={{
                  position: 'absolute', top: 8, left: 8, right: -8,
                  height: 420, borderRadius: 20,
                  background: 'rgba(32,201,151,0.12)',
                  border: '1px solid rgba(32,201,151,0.25)',
                }} />
                {/* Main card */}
                <Card shadow="xl" radius="xl" style={{ overflow: 'hidden', position: 'relative' }}>
                  {/* Image placeholder */}
                  <Box style={{
                    height: 220,
                    background: 'linear-gradient(135deg, #096e4f 0%, #20c997 50%, #63e6be 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <IconHome size={64} color="rgba(255,255,255,0.6)" />
                  </Box>
                  <Badge
                    variant="filled"
                    color="teal"
                    size="md"
                    style={{ position: 'absolute', top: 14, right: 14, fontWeight: 700 }}
                  >
                    94% match
                  </Badge>
                  <Box p="lg">
                    <Group justify="space-between" align="flex-start" mb="xs">
                      <div>
                        <Text fw={700} size="lg" style={{ color: '#212529' }}>Modern Studio</Text>
                        <Text size="sm" c="dimmed">Downtown, San Francisco</Text>
                      </div>
                      <Text fw={700} size="xl" c="teal.6">$1,850<Text span size="sm" c="dimmed">/mo</Text></Text>
                    </Group>
                    <Group gap="xs">
                      <Badge variant="light" color="teal" size="sm">1 bed</Badge>
                      <Badge variant="light" color="teal" size="sm">1 bath</Badge>
                      <Badge variant="light" size="sm">Furnished</Badge>
                    </Group>
                    <Group gap="lg" justify="center" mt="md">
                      <ActionIcon size={52} radius="xl" variant="light" color="red" style={{ boxShadow: '0 4px 16px rgba(255,107,107,0.2)' }}>
                        <IconX size={24} />
                      </ActionIcon>
                      <ActionIcon size={52} radius="xl" variant="filled" color="teal" style={{ boxShadow: '0 4px 16px rgba(32,201,151,0.3)' }}>
                        <IconHeart size={24} />
                      </ActionIcon>
                    </Group>
                  </Box>
                </Card>
              </Box>
            </Grid.Col>
          </Grid>
        </Container>
      </Box>

      {/* ── SECTION 2: FEATURES ──────────────────────────────── */}
      <Box className="section-padding" style={{ backgroundColor: '#ffffff' }}>
        <Container size="xl">
          <Stack align="center" gap="xs" mb={48}>
            <Title order={2} ta="center" style={{ color: '#212529' }}>
              Everything you need to find home
            </Title>
            <Text size="lg" c="dimmed" ta="center" maw={500}>
              Padly brings smart technology to the housing search so you spend less time searching and more time living.
            </Text>
          </Stack>
          <Grid gutter="lg">
            {[
              {
                icon: <IconSparkles size={24} color="#20c997" />,
                title: 'Smart Matching',
                desc: 'Our ML model ranks listings by your budget, lifestyle, and past swipes — getting smarter with every interaction.',
              },
              {
                icon: <IconUsers size={24} color="#20c997" />,
                title: 'Group Search',
                desc: 'Form or join a group to search together, compare listings, and split costs with people you actually want to live with.',
              },
              {
                icon: <IconShieldCheck size={24} color="#20c997" />,
                title: 'Verified Listings',
                desc: 'All listings are reviewed before appearing in your feed — no bots, no scams, no wasted time.',
              },
            ].map((feature, i) => (
              <Grid.Col key={i} span={{ base: 12, sm: 6, md: 4 }}>
                <Card className="card-lift" shadow="sm" radius="lg" p="xl" style={{ height: '100%', backgroundColor: '#ffffff', border: '1px solid #f1f3f5' }}>
                  <Stack gap="md">
                    <div className="feature-icon-bg">{feature.icon}</div>
                    <Title order={4} style={{ color: '#212529' }}>{feature.title}</Title>
                    <Text size="sm" c="dimmed" style={{ lineHeight: 1.65 }}>{feature.desc}</Text>
                  </Stack>
                </Card>
              </Grid.Col>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* ── SECTION 3: HOW IT WORKS ──────────────────────────── */}
      <Box className="section-padding" style={{ backgroundColor: '#f8f9fa' }}>
        <Container size="lg">
          <Stack align="center" gap="xs" mb={48}>
            <Title order={2} ta="center" style={{ color: '#212529' }}>How Padly works</Title>
            <Text size="lg" c="dimmed" ta="center">Four steps to your next home.</Text>
          </Stack>
          <Grid gutter="xl" align="center">
            {[
              { step: 1, icon: <IconUser size={24} color="#20c997" />, title: 'Create your profile', desc: 'Tell us about yourself — your lifestyle, work, and what you value in a home.' },
              { step: 2, icon: <IconSettings size={24} color="#20c997" />, title: 'Set preferences', desc: 'Define your budget, location, must-haves, and nice-to-haves.' },
              { step: 3, icon: <IconHeart size={24} color="#20c997" />, title: 'Swipe on listings', desc: 'Browse AI-ranked listings and swipe right on the ones you love.' },
              { step: 4, icon: <IconUsers size={24} color="#20c997" />, title: 'Connect & move in', desc: 'Match with compatible roommates and coordinate the move together.' },
            ].map((s, i) => (
              <Grid.Col key={i} span={{ base: 12, sm: 6, md: 3 }}>
                <Stack align="center" gap="md" ta="center">
                  <Box style={{
                    width: 64, height: 64, borderRadius: '50%',
                    background: 'rgba(32,201,151,0.10)',
                    border: '2px solid rgba(32,201,151,0.25)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    position: 'relative',
                  }}>
                    {s.icon}
                    <Box style={{
                      position: 'absolute', top: -8, right: -8,
                      width: 24, height: 24, borderRadius: '50%',
                      background: '#20c997', color: 'white',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, fontWeight: 700,
                    }}>
                      {s.step}
                    </Box>
                  </Box>
                  <Title order={5} style={{ color: '#212529' }}>{s.title}</Title>
                  <Text size="sm" c="dimmed">{s.desc}</Text>
                </Stack>
              </Grid.Col>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* ── SECTION 4: CTA BANNER (unauthenticated only) ─────── */}
      {!isLoading && !isAuthenticated && (
        <Box style={{ backgroundColor: '#20c997', padding: '5rem 0' }}>
          <Container size="md">
            <Stack align="center" gap="xl">
              <Title order={2} ta="center" style={{ color: '#ffffff' }}>
                Ready to find your place?
              </Title>
              <Text size="lg" ta="center" style={{ color: 'rgba(255,255,255,0.85)', maxWidth: 480 }}>
                Join thousands of students and early-career professionals who found their home on Padly.
              </Text>
              <Button size="xl" variant="white" color="teal" component={Link} href="/signup" style={{ fontWeight: 600 }}>
                Create Free Account
              </Button>
            </Stack>
          </Container>
        </Box>
      )}
    </Box>
  );
}
