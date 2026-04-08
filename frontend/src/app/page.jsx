'use client';

import { useEffect, useState, useRef } from 'react';
import { Box, Container, Grid, Stack, Group, Title, Text, Badge, Button, Card, ActionIcon } from '@mantine/core';
import { IconHeart, IconX, IconUsers, IconShieldCheck, IconSparkles, IconUser, IconSettings, IconArrowRight } from '@tabler/icons-react';
import Link from 'next/link';
import { Navigation } from './components/Navigation';
import { useAuth } from './contexts/AuthContext';
import { usePadlyTour } from './contexts/TourContext';

const DEMO_LISTINGS = [
  {
    title: 'Modern Studio Loft',
    city: 'San Francisco, CA',
    price: 1850,
    beds: 'Studio',
    baths: 1,
    tags: ['Furnished', 'Utilities incl.'],
    match: 94,
    image: 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&q=80',
  },
  {
    title: 'Bright 1BR near Campus',
    city: 'Toronto, ON',
    price: 1400,
    beds: 1,
    baths: 1,
    tags: ['Laundry', 'Pet friendly'],
    match: 88,
    image: 'https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600&q=80',
  },
  {
    title: 'Cozy 2BR Apartment',
    city: 'Austin, TX',
    price: 2100,
    beds: 2,
    baths: 2,
    tags: ['Parking', 'Gym'],
    match: 91,
    image: 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&q=80',
  },
  {
    title: 'Charming Heritage Unit',
    city: 'Montreal, QC',
    price: 1200,
    beds: 1,
    baths: 1,
    tags: ['Furnished', 'Balcony'],
    match: 86,
    image: 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600&q=80',
  },
];

function DemoSwipeCard() {
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(null); // 'left' | 'right' | null
  const [entering, setEntering] = useState(false);
  const dirRef = useRef('right');

  useEffect(() => {
    const interval = setInterval(() => {
      const dir = dirRef.current;
      setDirection(dir);
      dirRef.current = dir === 'right' ? 'left' : 'right';

      setTimeout(() => {
        setIndex(i => (i + 1) % DEMO_LISTINGS.length);
        setDirection(null);
        setEntering(true);
        setTimeout(() => setEntering(false), 350);
      }, 400);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const listing = DEMO_LISTINGS[index];
  const isLeaving = direction !== null;
  const isLike = direction === 'right';

  let transform;
  if (direction === 'right') transform = 'translateX(140%) rotate(22deg)';
  else if (direction === 'left') transform = 'translateX(-140%) rotate(-22deg)';
  else if (entering) transform = 'translateX(0) scale(0.96)';
  else transform = 'translateX(0) scale(1)';

  return (
    <Box style={{ position: 'relative', maxWidth: 320, margin: '0 auto', height: 460 }}>
      {/* Stacked cards behind */}
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

      {/* Animated card */}
      <Box style={{
        position: 'absolute', top: 0, left: 0, right: 0,
        transform,
        transition: isLeaving ? 'transform 0.4s ease-in' : entering ? 'none' : 'transform 0.35s ease-out',
        borderRadius: 20,
        overflow: 'hidden',
        boxShadow: '0 12px 40px rgba(0,0,0,0.13)',
        backgroundColor: '#fff',
      }}>
        {/* Colour overlay */}
        {isLeaving && (
          <Box style={{
            position: 'absolute', inset: 0, zIndex: 10, borderRadius: 20, pointerEvents: 'none',
            backgroundColor: isLike ? 'rgba(32,201,151,0.25)' : 'rgba(255,107,107,0.25)',
          }} />
        )}

        {/* LIKE / NOPE stamp */}
        {isLeaving && (
          <Box style={{
            position: 'absolute', top: 24, zIndex: 20, pointerEvents: 'none',
            ...(isLike ? { left: 20, transform: 'rotate(-12deg)' } : { right: 20, transform: 'rotate(12deg)' }),
            border: `3px solid ${isLike ? '#20c997' : '#ff6b6b'}`,
            borderRadius: 8, padding: '2px 10px',
          }}>
            <Text fw={800} size="lg" style={{ color: isLike ? '#20c997' : '#ff6b6b', letterSpacing: 3 }}>
              {isLike ? 'LIKE' : 'NOPE'}
            </Text>
          </Box>
        )}

        {/* Image */}
        <Box style={{ position: 'relative', height: 210, overflow: 'hidden', backgroundColor: '#f0f0f0' }}>
          <img
            src={listing.image}
            alt={listing.title}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
          <Badge
            variant="filled" color="teal" size="md"
            style={{ position: 'absolute', top: 12, right: 12, fontWeight: 700 }}
          >
            {listing.match}% match
          </Badge>
        </Box>

        {/* Info */}
        <Box p="lg">
          <Group justify="space-between" align="flex-start" mb="xs">
            <div>
              <Text fw={700} size="lg" style={{ color: '#212529' }}>{listing.title}</Text>
              <Text size="sm" c="dimmed">{listing.city}</Text>
            </div>
            <Text fw={700} size="xl" c="teal.6">
              ${listing.price.toLocaleString()}<Text span size="sm" c="dimmed">/mo</Text>
            </Text>
          </Group>
          <Group gap="xs" mb="md">
            <Badge variant="light" color="teal" size="sm">
              {listing.beds === 'Studio' ? 'Studio' : `${listing.beds} bed`}
            </Badge>
            <Badge variant="light" color="teal" size="sm">{listing.baths} bath</Badge>
            {listing.tags.map(t => <Badge key={t} variant="light" size="sm">{t}</Badge>)}
          </Group>
          <Group gap="lg" justify="center">
            <ActionIcon size={52} radius="xl" variant="light" color="red"
              style={{ boxShadow: '0 4px 16px rgba(255,107,107,0.2)' }}>
              <IconX size={24} />
            </ActionIcon>
            <ActionIcon size={52} radius="xl" variant="filled" color="teal"
              style={{ boxShadow: '0 4px 16px rgba(32,201,151,0.3)' }}>
              <IconHeart size={24} />
            </ActionIcon>
          </Group>
        </Box>
      </Box>
    </Box>
  );
}

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
                <Badge
                  variant="filled"
                  size="lg"
                  radius="xl"
                  style={{
                    width: 'fit-content',
                    background: 'linear-gradient(135deg, #099268 0%, #20c997 100%)',
                    color: '#fff',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    padding: '0.45rem 1.1rem',
                    boxShadow: '0 2px 12px rgba(32,201,151,0.35)',
                  }}
                >
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
                    </Group>
                  ) : (
                    <Stack gap="sm" style={{ maxWidth: 360 }}>
                      <Button size="lg" color="teal" component={Link} href="/signup" fullWidth>
                        Find Your Place
                      </Button>
                      <Box>
                        <Button
                          size="lg"
                          component={Link}
                          href="/preferences-setup"
                          fullWidth
                          rightSection={<IconArrowRight size={18} />}
                          style={{
                            background: 'linear-gradient(135deg, #0ca678 0%, #20c997 100%)',
                            color: '#fff',
                            border: '2px solid rgba(255,255,255,0.25)',
                            boxShadow: '0 0 0 0 rgba(32,201,151,0.5)',
                            animation: 'pulse-teal 2.2s ease-in-out infinite',
                          }}
                        >
                          Browse Listings
                        </Button>
                        <Text size="xs" ta="center" c="dimmed" mt={6}>
                          No account needed — start browsing instantly
                        </Text>
                      </Box>
                    </Stack>
                  )
                )}

              </Stack>
            </Grid.Col>

            <Grid.Col span={{ base: 12, md: 6 }}>
              <DemoSwipeCard />
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
