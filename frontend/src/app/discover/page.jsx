'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Container, Box, Text, Title, Button, Stack, Loader, ActionIcon, Group, Progress, Modal, Badge, Divider } from '@mantine/core';
import { useHotkeys } from '@mantine/hooks';
import { IconX, IconHeart, IconRefresh, IconInfoCircle, IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';
import { SwipeCard } from '../components/SwipeCard';

import { getLikedListings, saveLikedListing } from './likedListings';

// ── session helpers ─────────────────────────────────────────────────────────

const SWIPE_SESSION_KEY = 'padly_swipe_session_id';

/** Stable client label for swipe telemetry (backend requires algorithm_version). */
const DISCOVER_ALGORITHM_VERSION = 'discover-v1';

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
  const userId = user?.profile?.id;
  const router = useRouter();

  const [listings, setListings] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedListing, setExpandedListing] = useState(null);
  const [expandedImageIndex, setExpandedImageIndex] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const swipeSessionIdRef = useRef(null);
  const nextOffsetRef = useRef(0);

  const fetchRecommendations = useCallback(async ({ append = false } = {}) => {
    setLoading(true);
    setError(null);

    try {
      // Fetch user preferences
      let prefs = {};
      const swipedIds = new Set();
      if (userId && authState?.accessToken) {
        const prefRes = await fetch(`http://localhost:8000/api/preferences/${userId}`, {
          headers: { Authorization: `Bearer ${authState.accessToken}` },
        });
        if (prefRes.ok) {
          const prefData = await prefRes.json();
          prefs = prefData.data || prefData || {};
        }

        try {
          const swipesRes = await fetch('http://localhost:8000/api/interactions/swipes/me?limit=500', {
            headers: { Authorization: `Bearer ${authState.accessToken}` },
          });
          if (swipesRes.ok) {
            const swipesPayload = await swipesRes.json();
            for (const event of swipesPayload?.data || []) {
              if (event?.listing_id) swipedIds.add(event.listing_id);
            }
          }
        } catch {
          // Swipe history fetch is optional; fall back to local liked cache only.
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
        target_country: prefs.target_country ?? undefined,
        target_state_province: prefs.target_state_province ?? undefined,
        target_city: prefs.target_city ?? undefined,
        required_bedrooms: prefs.required_bedrooms ?? undefined,
        target_bathrooms: prefs.target_bathrooms ?? undefined,
        desired_beds:    prefs.required_bedrooms ?? undefined,
        desired_baths:   prefs.target_bathrooms  ?? undefined,
        target_deposit_amount: prefs.target_deposit_amount ?? undefined,
        furnished_preference: prefs.furnished_preference ?? undefined,
        gender_policy: prefs.gender_policy ?? undefined,
        target_lease_type: prefs.target_lease_type ?? undefined,
        target_lease_duration_months: prefs.target_lease_duration_months ?? undefined,
        move_in_date: prefs.move_in_date ?? undefined,
        target_furnished: prefs.target_furnished ?? undefined,
        wants_furnished:
          prefs.furnished_preference === 'required' || prefs.furnished_preference === 'preferred'
            ? 1
            : prefs.target_furnished === true
              ? 1
              : undefined,
        pref_lat:        prefs.target_latitude   ?? undefined,
        pref_lon:        prefs.target_longitude  ?? undefined,
        top_n: 50,
        offset: append ? nextOffsetRef.current : 0,
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

      // Filter out listings already seen via swipes or saved likes.
      const likedIds = new Set(getLikedListings().map((l) => l.listing_id));
      const fresh = (data.recommendations || []).filter(
        (l) => !likedIds.has(l.listing_id) && !swipedIds.has(l.listing_id)
      );

      setHasMore(Boolean(data.has_more));
      nextOffsetRef.current = (data.offset || 0) + (data.count || 0);

      if (append) {
        setListings((prev) => [...prev, ...fresh]);
      } else {
        setListings(fresh);
        setCurrentIndex(0);
        nextOffsetRef.current = (data.offset || 0) + (data.count || 0);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [userId, authState?.accessToken]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  useEffect(() => {
    setExpandedImageIndex(0);
  }, [expandedListing?.listing_id]);

  useEffect(() => {
    const remaining = listings.length - currentIndex;
    if (!loading && !error && hasMore && remaining === 0) {
      fetchRecommendations({ append: true });
    }
  }, [currentIndex, listings.length, loading, error, hasMore, fetchRecommendations]);

  const persistSwipeEvent = useCallback(async ({ listing, action, position, startedAt }) => {
    if (!authState?.accessToken || !userId || !listing?.listing_id) return;

    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }

    const algorithmVersion =
      listing?.algorithm_version != null && String(listing.algorithm_version).trim()
        ? String(listing.algorithm_version).trim()
        : DISCOVER_ALGORITHM_VERSION;

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
          algorithm_version: algorithmVersion,
          model_version: listing?.ml_score != null ? 'recommender-v1' : null,
          city_filter: listing.city ?? null,
          latency_ms:
            startedAt != null && typeof performance !== 'undefined'
              ? Math.max(0, Math.round(performance.now() - startedAt))
              : undefined,
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
    const action = direction === 'right' ? 'like' : 'pass';
    if (action === 'like') saveLikedListing(listing);

    // Feed position must match the card index in this session's stack (0-based).
    const top = listings[currentIndex];
    const position =
      top && listing?.listing_id === top.listing_id
        ? currentIndex
        : listings.findIndex((item) => item.listing_id === listing?.listing_id);
    const startedAt = typeof performance !== 'undefined' ? performance.now() : null;

    void persistSwipeEvent({
      listing,
      action,
      position: position >= 0 ? position : currentIndex,
      startedAt,
    });

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

  const handleModalAction = (direction) => {
    setExpandedListing(null);
    setTimeout(() => handleButton(direction), 200);
  };

  const remaining = listings.length - currentIndex;
  const isDone = !loading && !error && remaining === 0 && !hasMore;

  useHotkeys([
    ['ArrowLeft', () => handleButton('left')],
    ['ArrowRight', () => handleButton('right')],
  ]);

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
              <Group gap="md" justify="center">
                <Button
                  leftSection={<IconRefresh size={16} />}
                  onClick={fetchRecommendations}
                  color="teal"
                >
                  Reload
                </Button>
                <Button variant="light" color="teal" onClick={() => router.push('/matches')}>
                  View Matches
                </Button>
                <Button variant="outline" color="teal" onClick={() => router.push('/roommates')}>
                  Find roommate matches
                </Button>
              </Group>
            </Stack>
          )}

          {/* Card stack + buttons */}
          {!loading && !error && !isDone && (
            <>
              <Box style={{ width: '100%', maxWidth: 400, marginBottom: 16 }}>
                <Group justify="space-between" mb={6}>
                  <Text size="xs" c="dimmed">Listing {currentIndex + 1} of {listings.length}</Text>
                  <Text size="xs" c="dimmed">{listings.length - currentIndex - 1} remaining</Text>
                </Group>
                <Progress
                  value={listings.length > 0 ? ((currentIndex) / listings.length) * 100 : 0}
                  size="xs"
                  color="teal"
                  radius="xl"
                />
              </Box>

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
                      onExpand={setExpandedListing}
                    />
                  );
                })}
              </Box>

              {/* Action buttons */}
              <Group gap={48} justify="center" data-tour="discover-actions">
                <Stack align="center" gap={6}>
                  <ActionIcon
                    data-tour="discover-pass-btn"
                    size={64}
                    radius="xl"
                    variant="light"
                    color="red"
                    onClick={() => handleButton('left')}
                    style={{ boxShadow: '0 4px 20px rgba(255,107,107,0.20)', border: '2px solid #ffc9c9' }}
                  >
                    <IconX size={28} />
                  </ActionIcon>
                  <Text size="xs" c="dimmed" fw={500}>Pass</Text>
                </Stack>
                <Stack align="center" gap={6}>
                  <ActionIcon
                    data-tour="discover-like-btn"
                    size={64}
                    radius="xl"
                    variant="light"
                    color="teal"
                    onClick={() => handleButton('right')}
                    style={{ boxShadow: '0 4px 20px rgba(32,201,151,0.22)', border: '2px solid #96f2d7' }}
                  >
                    <IconHeart size={28} />
                  </ActionIcon>
                  <Text size="xs" c="dimmed" fw={500}>Like</Text>
                </Stack>
              </Group>
              <Text size="xs" c="dimmed" ta="center" visibleFrom="sm" mt="xs">← Pass · → Like</Text>
            </>
          )}

        </Stack>
      </Container>

      {/* Quick-view modal */}
      <Modal
        opened={!!expandedListing}
        onClose={() => setExpandedListing(null)}
        size="lg"
        padding={0}
        radius="lg"
        centered
        overlayProps={{ backgroundOpacity: 0.5, blur: 6 }}
        transitionProps={{ transition: 'slide-up', duration: 300 }}
        withCloseButton={false}
      >
        {expandedListing && (() => {
          const imgs = (() => {
            const i = expandedListing?.images;
            if (Array.isArray(i)) return i;
            if (typeof i === 'string') { try { return JSON.parse(i); } catch { return []; } }
            return [];
          })();
          const safeImageIndex = imgs.length > 0
            ? Math.min(expandedImageIndex, imgs.length - 1)
            : 0;
          const heroImage = imgs[safeImageIndex] || 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080';

          const amenities = expandedListing.amenities && typeof expandedListing.amenities === 'object'
            ? expandedListing.amenities
            : {};

          const bedsLabel = expandedListing.number_of_bedrooms === 0
            ? 'Studio'
            : expandedListing.number_of_bedrooms != null
              ? String(expandedListing.number_of_bedrooms)
              : '—';

          return (
            <Box>
              {/* Hero image */}
              <Box style={{ position: 'relative', height: 300, overflow: 'hidden', borderRadius: '12px 12px 0 0' }}>
                <ImageWithFallback
                  src={heroImage}
                  alt={expandedListing.title || 'Listing'}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />

                {imgs.length > 1 && (
                  <>
                    <Box
                      style={{
                        position: 'absolute',
                        top: '50%',
                        left: 12,
                        transform: 'translateY(-50%)',
                      }}
                    >
                      <ActionIcon
                        variant="filled"
                        color="dark"
                        radius="xl"
                        size="lg"
                        onClick={() => setExpandedImageIndex((prev) => (prev - 1 + imgs.length) % imgs.length)}
                        style={{ opacity: 0.85 }}
                      >
                        <IconChevronLeft size={18} />
                      </ActionIcon>
                    </Box>
                    <Box
                      style={{
                        position: 'absolute',
                        top: '50%',
                        right: 12,
                        transform: 'translateY(-50%)',
                      }}
                    >
                      <ActionIcon
                        variant="filled"
                        color="dark"
                        radius="xl"
                        size="lg"
                        onClick={() => setExpandedImageIndex((prev) => (prev + 1) % imgs.length)}
                        style={{ opacity: 0.85 }}
                      >
                        <IconChevronRight size={18} />
                      </ActionIcon>
                    </Box>
                  </>
                )}

                {/* Close button */}
                <Box
                  style={{
                    position: 'absolute', top: 14, left: 14,
                    backgroundColor: 'rgba(0,0,0,0.45)',
                    borderRadius: '50%',
                  }}
                >
                  <ActionIcon
                    variant="subtle"
                    color="white"
                    size="lg"
                    radius="xl"
                    onClick={() => setExpandedListing(null)}
                    style={{ color: '#fff' }}
                  >
                    <IconX size={18} />
                  </ActionIcon>
                </Box>

                {/* Match badge */}
                {expandedListing.match_percent && (
                  <Badge
                    variant="filled"
                    color="teal"
                    size="md"
                    radius="sm"
                    style={{ position: 'absolute', top: 14, right: 14, fontWeight: 700 }}
                  >
                    {expandedListing.match_percent} match
                  </Badge>
                )}

                {imgs.length > 1 && (
                  <Badge
                    variant="filled"
                    color="dark"
                    size="sm"
                    radius="sm"
                    style={{ position: 'absolute', bottom: 14, right: 14, fontWeight: 700 }}
                  >
                    {safeImageIndex + 1} / {imgs.length}
                  </Badge>
                )}

                {/* Bottom gradient + title overlay */}
                <Box style={{
                  position: 'absolute', bottom: 0, left: 0, right: 0,
                  background: 'linear-gradient(to top, rgba(0,0,0,0.72) 0%, transparent 100%)',
                  padding: '2rem 1.25rem 1rem',
                }}>
                  <Text fw={700} size="xl" style={{ color: '#fff', lineHeight: 1.2 }} lineClamp={2}>
                    {expandedListing.title || 'Listing'}
                  </Text>
                  {expandedListing.city && (
                    <Text size="sm" style={{ color: 'rgba(255,255,255,0.80)', marginTop: 2 }}>
                      {expandedListing.city}
                    </Text>
                  )}
                </Box>
              </Box>

              {imgs.length > 1 && (
                <Group
                  gap="xs"
                  wrap="nowrap"
                  style={{
                    overflowX: 'auto',
                    padding: '0.75rem 1rem 0',
                  }}
                >
                  {imgs.map((img, index) => (
                    <Box
                      key={`${expandedListing.listing_id || expandedListing.title || 'listing'}-${index}`}
                      onClick={() => setExpandedImageIndex(index)}
                      style={{
                        minWidth: 72,
                        width: 72,
                        height: 56,
                        borderRadius: 10,
                        overflow: 'hidden',
                        cursor: 'pointer',
                        border: index === safeImageIndex ? '2px solid #12b886' : '2px solid transparent',
                        boxShadow: index === safeImageIndex ? '0 0 0 1px rgba(18,184,134,0.18)' : 'none',
                        backgroundColor: '#f3f4f6',
                        flexShrink: 0,
                      }}
                    >
                      <ImageWithFallback
                        src={img}
                        alt={`${expandedListing.title || 'Listing'} ${index + 1}`}
                        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                      />
                    </Box>
                  ))}
                </Group>
              )}

              {/* Details section */}
              <Box style={{ padding: '1.5rem' }}>

                {/* Row 1: price + property type */}
                <Group justify="space-between" align="center" mb="md">
                  {expandedListing.price_per_month != null && (
                    <Text fw={800} size="xl" c="teal.6">
                      ${Number(expandedListing.price_per_month).toLocaleString()}/mo
                    </Text>
                  )}
                  {expandedListing.property_type && (
                    <Badge variant="light" color="teal" size="md" radius="sm">
                      {expandedListing.property_type}
                    </Badge>
                  )}
                </Group>

                {/* Row 2: key stats */}
                <Group gap="sm" mb="md" grow>
                  <Box style={{
                    flex: 1, textAlign: 'center', padding: '0.75rem',
                    backgroundColor: '#f8f9fa', borderRadius: 10,
                  }}>
                    <Text fw={700} size="lg" style={{ color: '#212529' }}>{bedsLabel}</Text>
                    <Text size="xs" c="dimmed">Beds</Text>
                  </Box>
                  <Box style={{
                    flex: 1, textAlign: 'center', padding: '0.75rem',
                    backgroundColor: '#f8f9fa', borderRadius: 10,
                  }}>
                    <Text fw={700} size="lg" style={{ color: '#212529' }}>
                      {expandedListing.number_of_bathrooms != null ? expandedListing.number_of_bathrooms : '—'}
                    </Text>
                    <Text size="xs" c="dimmed">Baths</Text>
                  </Box>
                  <Box style={{
                    flex: 1, textAlign: 'center', padding: '0.75rem',
                    backgroundColor: '#f8f9fa', borderRadius: 10,
                  }}>
                    <Text fw={700} size="lg" style={{ color: '#212529' }}>
                      {expandedListing.area_sqft != null ? expandedListing.area_sqft : '—'}
                    </Text>
                    <Text size="xs" c="dimmed">Sqft</Text>
                  </Box>
                </Group>

                <Divider mb="md" />

                {/* Row 3: details grid */}
                <Box style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '0.5rem 1.5rem',
                  marginBottom: '1rem',
                }}>
                  {expandedListing.available_from && (
                    <>
                      <Text size="xs" c="dimmed" fw={600} style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>Available from</Text>
                      <Text size="sm">{expandedListing.available_from}</Text>
                    </>
                  )}
                  {expandedListing.lease_type && (
                    <>
                      <Text size="xs" c="dimmed" fw={600} style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>Lease type</Text>
                      <Text size="sm">{expandedListing.lease_type}</Text>
                    </>
                  )}
                  <>
                    <Text size="xs" c="dimmed" fw={600} style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>Furnished</Text>
                    <Text size="sm">{expandedListing.furnished ? 'Yes' : 'No'}</Text>
                  </>
                  {expandedListing.utilities_included != null && (
                    <>
                      <Text size="xs" c="dimmed" fw={600} style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>Utilities</Text>
                      <Text size="sm">{expandedListing.utilities_included ? 'Included' : 'Not included'}</Text>
                    </>
                  )}
                </Box>

                {/* Row 4: amenities */}
                {Object.entries(amenities).filter(([, v]) => v).length > 0 && (
                  <Group gap="xs" mb="md" wrap="wrap">
                    {Object.entries(amenities)
                      .filter(([, v]) => v)
                      .map(([key]) => (
                        <Badge key={key} variant="light" color="teal" size="sm" radius="sm">
                          {key}
                        </Badge>
                      ))}
                  </Group>
                )}

                {/* Row 5: description */}
                {expandedListing.description && (
                  <Text size="sm" c="dimmed" lineClamp={3} mb="md" style={{ lineHeight: 1.6 }}>
                    {expandedListing.description}
                  </Text>
                )}

                {/* Row 6: action buttons */}
                <Group gap="sm" grow mt="xs">
                  <Button
                    color="red"
                    variant="light"
                    leftSection={<IconX size={16} />}
                    onClick={() => handleModalAction('left')}
                    radius="md"
                  >
                    Pass
                  </Button>
                  <Button
                    color="teal"
                    leftSection={<IconHeart size={16} />}
                    onClick={() => handleModalAction('right')}
                    radius="md"
                  >
                    Like this place
                  </Button>
                </Group>

              </Box>
            </Box>
          );
        })()}
      </Modal>

    </Box>
  );
}
