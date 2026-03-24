'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Container, Box, Text, Title, Button, Stack, Loader, ActionIcon, Group } from '@mantine/core';
import { IconX, IconHeart, IconRefresh } from '@tabler/icons-react';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';
import { SwipeCard } from '../components/SwipeCard';

import { getLikedListings, saveLikedListing } from './likedListings';

// ── dummy cards shown during the guided tour ────────────────────────────────
const TOUR_DUMMY_LISTINGS = [
  {
    listing_id: 'tour-dummy-1',
    title: 'Sunny Studio near Campus',
    city: 'San Francisco',
    number_of_bedrooms: 1,
    number_of_bathrooms: 1,
    area_sqft: 550,
    furnished: true,
    price_per_month: 1850,
    match_percent: '92%',
    images: ['https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800'],
  },
  {
    listing_id: 'tour-dummy-2',
    title: 'Cozy 2BR with Rooftop Access',
    city: 'Los Angeles',
    number_of_bedrooms: 2,
    number_of_bathrooms: 1,
    area_sqft: 850,
    furnished: false,
    price_per_month: 2400,
    match_percent: '87%',
    images: ['https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800'],
  },
  {
    listing_id: 'tour-dummy-3',
    title: 'Modern Loft Downtown',
    city: 'New York',
    number_of_bedrooms: 1,
    number_of_bathrooms: 1,
    area_sqft: 700,
    furnished: true,
    price_per_month: 2100,
    match_percent: '95%',
    images: ['https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=800'],
  },
];

// ── session helpers ─────────────────────────────────────────────────────────

const SWIPE_SESSION_KEY = 'padly_swipe_session_id';

function getOrCreateSwipeSessionId() {
  if (typeof window === 'undefined') return 'server-session';
  const existing = sessionStorage.getItem(SWIPE_SESSION_KEY);
  if (existing) return existing;

  const generated = typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  sessionStorage.setItem(SWIPE_SESSION_KEY, generated);
  return generated;
}

// ── page ────────────────────────────────────────────────────────────────────

export default function DiscoverPage() {
  return (
    <ProtectedRoute>
      <DiscoverContent />
    </ProtectedRoute>
  );
}

function DiscoverContent() {
  const { user, authState } = useAuth();
  const { tourPhase } = usePadlyTour();
  const isTourDiscover = tourPhase === 'discover';
  const userId = user?.profile?.id;
  const router = useRouter();

  const [listings, setListings] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const swipeSessionIdRef = useRef(null);

  const fetchRecommendations = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch user preferences
      let prefs = {};
      if (userId && authState?.accessToken) {
        const prefRes = await fetch(`http://localhost:8000/api/preferences/${userId}`, {
          headers: { Authorization: `Bearer ${authState.accessToken}` },
        });
        if (prefRes.ok) {
          const prefData = await prefRes.json();
          prefs = prefData.data || prefData || {};
        }
      }

      // Build liked-listing averages to personalise the model
      const liked = getLikedListings();
      const likedExtras = {};
      let behaviorSampleSize;

      // Prefer persisted behavior features from backend (Phase 2A).
      if (authState?.accessToken) {
        try {
          const behaviorRes = await fetch('http://localhost:8000/api/interactions/behavior/me?days=180', {
            headers: { Authorization: `Bearer ${authState.accessToken}` },
          });
          if (behaviorRes.ok) {
            const behaviorPayload = await behaviorRes.json();
            const behavior = behaviorPayload?.data || {};
            if (behavior.liked_mean_price != null) likedExtras.liked_mean_price = behavior.liked_mean_price;
            if (behavior.liked_mean_beds != null) likedExtras.liked_mean_beds = behavior.liked_mean_beds;
            if (behavior.liked_mean_sqfeet != null) likedExtras.liked_mean_sqfeet = behavior.liked_mean_sqfeet;
            if (behavior.sample_size != null) behaviorSampleSize = behavior.sample_size;
          }
        } catch {
          // Behavior vector is optional in Phase 2A.
        }
      }

      // Fallback to local in-session liked cache when backend behavior data is sparse.
      if (liked.length > 0) {
        const avg = (arr) => arr.filter(Boolean).reduce((a, b) => a + b, 0) / arr.filter(Boolean).length;
        if (likedExtras.liked_mean_price == null) likedExtras.liked_mean_price = avg(liked.map((l) => l.price_per_month));
        if (likedExtras.liked_mean_beds == null) likedExtras.liked_mean_beds = avg(liked.map((l) => l.number_of_bedrooms));
        if (likedExtras.liked_mean_sqfeet == null) likedExtras.liked_mean_sqfeet = avg(liked.map((l) => l.area_sqft));
      }

      const body = {
        budget_min:      prefs.budget_min     ?? undefined,
        budget_max:      prefs.budget_max     ?? undefined,
        desired_beds:    prefs.required_bedrooms ?? undefined,
        desired_baths:   prefs.target_bathrooms  ?? undefined,
        wants_furnished:
          prefs.furnished_preference === 'required' || prefs.furnished_preference === 'preferred'
            ? 1
            : prefs.target_furnished === true
              ? 1
              : undefined,
        pref_lat:        prefs.target_latitude   ?? undefined,
        pref_lon:        prefs.target_longitude  ?? undefined,
        top_n: 30,
        behavior_sample_size: behaviorSampleSize,
        ...likedExtras,
      };

      const res = await fetch('http://localhost:8000/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error('Failed to fetch recommendations');

      const data = await res.json();

      // Filter out listings already liked
      const likedIds = new Set(getLikedListings().map((l) => l.listing_id));
      const fresh = (data.recommendations || []).filter((l) => !likedIds.has(l.listing_id));

      setListings(fresh);
      setCurrentIndex(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [userId, authState?.accessToken]);

  useEffect(() => {
    if (isTourDiscover) {
      setListings(TOUR_DUMMY_LISTINGS);
      setCurrentIndex(0);
      setLoading(false);
      setError(null);
      return;
    }
    fetchRecommendations();
  }, [fetchRecommendations, isTourDiscover]);

  const persistSwipeEvent = useCallback(async ({ listing, action, position }) => {
    if (!authState?.accessToken || !userId || !listing?.listing_id) return;

    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }

    try {
      const response = await fetch('http://localhost:8000/api/interactions/swipes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify({
          listing_id: listing.listing_id,
          action,
          surface: 'discover',
          session_id: swipeSessionIdRef.current,
          position_in_feed: position,
          algorithm_version: listing?.algorithm_version || 'phase2b-cold-no-ml',
          model_version: listing?.ml_score != null ? 'recommender-v1' : null,
          city_filter: listing.city ?? null,
        }),
      });

      // Do not disrupt UX on telemetry failures.
      if (!response.ok && response.status !== 503) {
        console.warn('Failed to persist swipe interaction');
      }
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken, userId]);

  const handleSwipe = useCallback((direction, listing) => {
    const isDummy = listing?.listing_id?.startsWith('tour-dummy');

    if (!isDummy) {
      const action = direction === 'right' ? 'like' : 'pass';
      if (action === 'like') saveLikedListing(listing);

      const position = listings.findIndex((item) => item.listing_id === listing?.listing_id);
      void persistSwipeEvent({
        listing,
        action,
        position: position >= 0 ? position : currentIndex,
      });
    }

    setCurrentIndex((prev) => prev + 1);

    if (tourPhase === 'discover') {
      window.dispatchEvent(new CustomEvent('padly-tour-swipe', {
        detail: { direction },
      }));
    }
  }, [currentIndex, listings, persistSwipeEvent, tourPhase]);

  const handleButton = (direction) => {
    if (currentIndex >= listings.length) return;
    handleSwipe(direction, listings[currentIndex]);
  };

  const remaining = listings.length - currentIndex;
  const isDone = !loading && !error && remaining === 0;

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#fafafa' }}>
      <Navigation />

      <Container size="sm" style={{ padding: '2rem 1rem' }}>
        {/* Header */}
        <Stack align="center" gap={4} mb="xl">
          <Title order={2} style={{ color: '#111', fontWeight: 500 }}>
            Discover
          </Title>
          {!loading && !isDone && (
            <Text size="sm" c="dimmed" data-tour="discover-counter">
              {remaining} listing{remaining !== 1 ? 's' : ''} left
            </Text>
          )}
        </Stack>

        {/* Content */}
        <Stack align="center" gap="xl">

          {/* Loading */}
          {loading && (
            <Stack align="center" gap="md" style={{ height: 520, justifyContent: 'center' }}>
              <Loader size="lg" color="#20c997" />
              <Text c="dimmed">Finding listings for you…</Text>
            </Stack>
          )}

          {/* Error */}
          {!loading && error && (
            <Stack align="center" gap="md" style={{ height: 520, justifyContent: 'center' }}>
              <Text c="red">{error}</Text>
              <Button onClick={fetchRecommendations} variant="light" color="teal">
                Try again
              </Button>
            </Stack>
          )}

          {/* Done */}
          {isDone && (
            <Stack align="center" gap="lg" style={{ height: 520, justifyContent: 'center' }}>
              <Text style={{ fontSize: '3.5rem' }}>🏠</Text>
              <Title order={3} style={{ color: '#111' }}>You've seen everything!</Title>
              <Text c="dimmed" ta="center" maw={320}>
                Check your liked listings in Matches, or reload for a fresh batch.
              </Text>
              <Group gap="md">
                <Button
                  leftSection={<IconRefresh size={16} />}
                  onClick={fetchRecommendations}
                  style={{ backgroundColor: '#20c997' }}
                >
                  Reload
                </Button>
                <Button variant="light" color="teal" onClick={() => router.push('/matches')}>
                  View Matches
                </Button>
              </Group>
            </Stack>
          )}

          {/* Card stack + buttons */}
          {!loading && !error && !isDone && (
            <>
              <Box data-tour="discover-card" style={{ position: 'relative', width: '100%', maxWidth: 400, height: 520 }}>
                {[2, 1, 0].map((offset) => {
                  const idx = currentIndex + offset;
                  if (idx >= listings.length) return null;
                  return (
                    <SwipeCard
                      key={listings[idx].listing_id}
                      listing={listings[idx]}
                      onSwipe={handleSwipe}
                      isTop={offset === 0}
                      stackOffset={offset}
                    />
                  );
                })}
              </Box>

              {/* Action buttons */}
              <Group gap={48} justify="center" data-tour="discover-actions">
                <ActionIcon
                  data-tour="discover-pass-btn"
                  size={64}
                  radius="xl"
                  variant="light"
                  color="red"
                  onClick={() => handleButton('left')}
                  style={{ boxShadow: '0 4px 16px rgba(255,107,107,0.25)' }}
                >
                  <IconX size={28} />
                </ActionIcon>
                <ActionIcon
                  data-tour="discover-like-btn"
                  size={64}
                  radius="xl"
                  variant="light"
                  color="teal"
                  onClick={() => handleButton('right')}
                  style={{ boxShadow: '0 4px 16px rgba(32,201,151,0.25)' }}
                >
                  <IconHeart size={28} />
                </ActionIcon>
              </Group>
            </>
          )}

        </Stack>
      </Container>
    </Box>
  );
}
