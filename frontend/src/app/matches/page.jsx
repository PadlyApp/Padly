'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

import { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Container, Title, Text, Grid, Card, Badge, Button, Stack, Box, ThemeIcon, Group, Tooltip } from '@mantine/core';
import { SkeletonListingCard } from '../components/Skeletons';
import { IconSparkles, IconBookmark, IconBookmarkFilled, IconMapPin } from '@tabler/icons-react';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { useAuth } from '../contexts/AuthContext';
import { usePageTracking } from '../hooks/usePageTracking';
import { getLikedListings } from '../discover/likedListings';
import { formatAmenityLabel } from '../../../lib/formatters';
import {
  createAppError,
  hasCompleteCorePreferences,
  normalizeRecommendationsError,
  parseApiErrorResponse,
} from '../../../lib/errorHandling';

export default function MatchesPage() {
  return (
    <ProtectedRoute>
      <MatchesPageContent />
    </ProtectedRoute>
  );
}

function parseListingTitle(title) {
  if (!title) return { street: '', location: '' };
  const parts = title.split('|');
  if (parts.length >= 2) {
    return { street: parts[0].trim(), location: parts.slice(1).join(' ').trim() };
  }
  return { street: title.trim(), location: '' };
}

function MatchesPageContent() {
  const router = useRouter();
  const { user, getValidToken } = useAuth();
  const userId = user?.profile?.id;

  usePageTracking('matches', authState?.accessToken);

  const [listings, setListings] = useState([]);
  const [missingCorePreferences, setMissingCorePreferences] = useState(false);
  const [userGroup, setUserGroup] = useState(null);
  const [savedListingIds, setSavedListingIds] = useState(new Set());
  // Tracks the last feedData object seen so we only sync on a genuine new result
  const prevFeedDataRef = useRef(null);

  // ── cached recommendations (5-min stale time, shared QueryClient) ─────────

  const fetchMatchesFeed = useCallback(async () => {
    const token = await getValidToken();
    if (!token) throw new Error('Not authenticated');

    let prefs = {};
    let hasCorePreferences = false;
    let behaviorSampleSize;
    const liked = getLikedListings();
    const likedExtras = {};

    const prefRes = await fetch(`${API_BASE}/api/preferences/${userId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (prefRes.ok) {
      const prefData = await prefRes.json();
      prefs = prefData.data || prefData || {};
      hasCorePreferences = hasCompleteCorePreferences(prefs);
    }

    if (!hasCorePreferences) {
      return { listings: [], missingCorePreferences: true };
    }

    try {
      const behaviorRes = await fetch(`${API_BASE}/api/interactions/behavior/me?days=180`, {
        headers: { Authorization: `Bearer ${token}` },
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
      // Behavior vector is optional.
    }

    if (liked.length > 0) {
      const avg = (arr) => arr.filter(Boolean).reduce((a, b) => a + b, 0) / arr.filter(Boolean).length;
      if (likedExtras.liked_mean_price == null) likedExtras.liked_mean_price = avg(liked.map((l) => l.price_per_month));
      if (likedExtras.liked_mean_beds == null) likedExtras.liked_mean_beds = avg(liked.map((l) => l.number_of_bedrooms));
      if (likedExtras.liked_mean_sqfeet == null) likedExtras.liked_mean_sqfeet = avg(liked.map((l) => l.area_sqft));
    }

    const body = {
      budget_min: prefs.budget_min ?? undefined,
      budget_max: prefs.budget_max ?? undefined,
      target_country: prefs.target_country ?? undefined,
      target_state_province: prefs.target_state_province ?? undefined,
      target_city: prefs.target_city ?? undefined,
      required_bedrooms: prefs.required_bedrooms ?? undefined,
      target_bathrooms: prefs.target_bathrooms ?? undefined,
      desired_beds: prefs.required_bedrooms ?? undefined,
      desired_baths: prefs.target_bathrooms ?? undefined,
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
      pref_lat: prefs.target_latitude ?? undefined,
      pref_lon: prefs.target_longitude ?? undefined,
      top_n: 100,
      offset: 0,
      behavior_sample_size: behaviorSampleSize,
      ...likedExtras,
    };

    const res = await fetch(`${API_BASE}/api/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const apiError = await parseApiErrorResponse(res, 'Failed to fetch recommendations');
      throw createAppError(apiError.message, {
        status: apiError.status,
        payload: apiError.payload,
        rawMessage: apiError.message,
      });
    }

    const data = await res.json();
    return { listings: data.recommendations || [], missingCorePreferences: false };
  }, [userId, getValidToken]);

  const {
    data: feedData,
    isLoading: feedLoading,
    error: feedQueryError,
    refetch: refetchFeed,
  } = useQuery({
    queryKey: ['matches-feed', userId],
    queryFn: fetchMatchesFeed,
    enabled: !!userId,
    staleTime: 5 * 60 * 1000,
    gcTime:    10 * 60 * 1000,
    retry: false,
  });

  // Sync query data → state without a visible flash on cache-hit remounts
  useLayoutEffect(() => {
    if (!feedData || feedData === prevFeedDataRef.current) return;
    prevFeedDataRef.current = feedData;
    setListings(feedData.listings);
    setMissingCorePreferences(feedData.missingCorePreferences);
  }, [feedData]);

  const loading = feedLoading && !feedData;
  const error = feedQueryError ? normalizeRecommendationsError(feedQueryError) : null;

  // ── group + saved listings (cheap; runs once per auth session) ────────────

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    const fetchGroup = async () => {
      try {
        const token = await getValidToken();
        if (!token || cancelled) return;
        const res = await fetch(`${API_BASE}/api/roommate-groups?my_groups=true&limit=1`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        const group = data.data?.[0] || null;
        if (!group || cancelled) return;
        setUserGroup(group);

        const savedRes = await fetch(
          `${API_BASE}/api/interactions/swipes/groups/${group.id}/saved`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        const savedData = await savedRes.json();
        if (!cancelled) setSavedListingIds(new Set(savedData.saved_listing_ids || []));
      } catch (e) {
        console.error('[recommendations] fetchGroup error:', e);
      }
    };
    fetchGroup();
    return () => { cancelled = true; };
  }, [userId, getValidToken]);

  const handleGroupSave = async (e, listing) => {
    e.stopPropagation();
    if (!userGroup) return;
    const token = await getValidToken();
    if (!token) return;
    const lid = listing.listing_id || listing.id;
    const isSaved = savedListingIds.has(lid);

    setSavedListingIds(prev => {
      const next = new Set(prev);
      isSaved ? next.delete(lid) : next.add(lid);
      return next;
    });

    try {
      const res = await fetch(
        `${API_BASE}/api/interactions/swipes/groups/${userGroup.id}/save/${lid}`,
        {
          method: isSaved ? 'DELETE' : 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Save failed');
    } catch (e) {
      console.error('[recommendations] save error:', e);
      setSavedListingIds(prev => {
        const next = new Set(prev);
        isSaved ? next.add(lid) : next.delete(lid);
        return next;
      });
    }
  };

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#f8f9fa' }}>
      <Navigation />

      <Container size="xl" style={{ padding: '4rem 3rem' }} data-tour="matches-content">
        <Stack align="center" gap="sm" mb={48}>
          <Title
            order={1}
            style={{ fontSize: '2.5rem', fontWeight: 600, color: '#111', textAlign: 'center' }}
          >
            Recommendations
          </Title>
          <Text size="lg" c="dimmed" style={{ maxWidth: '42rem', textAlign: 'center' }}>
            Your top listings, ranked by preferences and activity
          </Text>
          {!loading && !error && listings.length > 0 && (
            <Text size="sm" c="dimmed">
              {listings.length} listings found
            </Text>
          )}
        </Stack>

        {loading && (
          <Grid gutter="lg">
            {Array.from({ length: 6 }).map((_, i) => (
              <Grid.Col key={i} span={{ base: 12, sm: 6, lg: 4 }}>
                <SkeletonListingCard />
              </Grid.Col>
            ))}
          </Grid>
        )}

        {!loading && error && (
          <Stack align="center" gap="lg" style={{ paddingTop: '6rem', paddingBottom: '6rem' }}>
            <Text size="md" c="red">{error}</Text>
            <Button size="md" color="teal" onClick={refetchFeed}>
              Retry
            </Button>
          </Stack>
        )}

        {!loading && !error && listings.length === 0 && (
          <Stack align="center" gap="lg" style={{ paddingTop: '6rem', paddingBottom: '6rem' }}>
            <ThemeIcon size={72} radius="xl" variant="light" color="teal">
              <IconSparkles size={36} />
            </ThemeIcon>
            <Stack align="center" gap="xs">
              <Title order={3} style={{ color: '#212529' }}>
                {missingCorePreferences ? 'Complete your preferences to get recommendations' : 'No recommendations yet'}
              </Title>
              <Text size="md" c="dimmed" ta="center" maw={420}>
                {missingCorePreferences
                  ? 'Set your country, state/province, and city to start receiving personalised listings.'
                  : 'Update your preferences or broaden a constraint to surface more listings.'}
              </Text>
            </Stack>
            <Stack gap="sm" align="center">
              <Button
                size="md"
                variant="light"
                color="teal"
                onClick={() => router.push('/account?tab=preferences')}
              >
                Open Preferences
              </Button>
              <Button size="md" color="teal" onClick={() => router.push('/discover')}>
                Go to Discover
              </Button>
            </Stack>
          </Stack>
        )}

        {!loading && !error && listings.length > 0 && (
          <Grid gutter="lg">
            {listings.map((listing) => {
              const image =
                listing.images?.[0] ||
                'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080';

              const { street, location } = parseListingTitle(listing.title);

              const amenityBadges = listing.amenities && typeof listing.amenities === 'object'
                ? Object.entries(listing.amenities).filter(([, v]) => v).slice(0, 2).map(([key]) => key)
                : [];

              const lid = listing.listing_id || listing.id;
              const saved = savedListingIds.has(lid);

              return (
                <Grid.Col key={listing.listing_id} span={{ base: 12, sm: 6, lg: 4 }}>
                  <Card
                    className="card-lift"
                    shadow="sm"
                    radius="lg"
                    style={{
                      overflow: 'hidden',
                      border: '1px solid #e9ecef',
                      cursor: 'pointer',
                      backgroundColor: '#fff',
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                    onClick={() => router.push(`/listings/${listing.listing_id}`)}
                  >
                    <Card.Section style={{ position: 'relative' }}>
                      <Box style={{ position: 'relative', paddingBottom: '66%', overflow: 'hidden', backgroundColor: '#f0f0f0' }}>
                        <ImageWithFallback
                          src={image}
                          alt={listing.title}
                          style={{
                            position: 'absolute', top: 0, left: 0,
                            width: '100%', height: '100%', objectFit: 'cover',
                          }}
                        />
                      </Box>
                      {listing.match_percent && (
                        <Badge
                          variant="filled"
                          color="teal"
                          size="md"
                          style={{ position: 'absolute', top: 12, right: 12, fontWeight: 700 }}
                        >
                          {listing.match_percent} match
                        </Badge>
                      )}
                    </Card.Section>

                    <Stack gap="xs" style={{ padding: '1.25rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                      {/* Address */}
                      <Box>
                        <Text
                          fw={600}
                          size="md"
                          lineClamp={1}
                          style={{ color: '#111', lineHeight: 1.4 }}
                          title={street}
                        >
                          {street || listing.title}
                        </Text>
                        {location && (
                          <Group gap={4} mt={2}>
                            <IconMapPin size={12} color="#868e96" style={{ flexShrink: 0 }} />
                            <Text size="xs" c="dimmed" lineClamp={1} style={{ flex: 1 }}>
                              {location}
                            </Text>
                          </Group>
                        )}
                      </Box>

                      {/* Details row */}
                      <Text size="sm" c="dimmed">
                        {[
                          listing.number_of_bedrooms != null && (listing.number_of_bedrooms === 0 ? 'Studio' : `${listing.number_of_bedrooms} Bed`),
                          listing.number_of_bathrooms != null && `${listing.number_of_bathrooms} Bath`,
                          listing.area_sqft && `${Number(listing.area_sqft).toLocaleString()} sq ft`,
                        ].filter(Boolean).join(' · ')}
                      </Text>

                      {/* Badges */}
                      {(listing.furnished || amenityBadges.length > 0) && (
                        <Group gap="xs">
                          {listing.furnished && (
                            <Badge variant="light" color="teal" size="sm">Furnished</Badge>
                          )}
                          {amenityBadges.map((key) => (
                            <Badge key={key} variant="light" color="gray" size="sm">
                              {formatAmenityLabel(key)}
                            </Badge>
                          ))}
                        </Group>
                      )}

                      {/* Price */}
                      {listing.price_per_month && (
                        <Text fw={700} size="xl" c="teal.6" style={{ marginTop: 'auto', paddingTop: '0.5rem' }}>
                          ${Number(listing.price_per_month).toLocaleString()}/mo
                        </Text>
                      )}

                      {/* Actions */}
                      <Stack gap="xs" mt="xs">
                        <Button
                          fullWidth
                          radius="md"
                          size="sm"
                          color="teal"
                          onClick={(e) => { e.stopPropagation(); router.push(`/listings/${listing.listing_id}`); }}
                        >
                          View Details
                        </Button>
                        {userGroup && (
                          <Tooltip
                            label={saved ? `Remove from ${userGroup.group_name}` : `Save to ${userGroup.group_name}`}
                            withArrow
                          >
                            <Button
                              fullWidth
                              radius="md"
                              size="sm"
                              variant={saved ? 'filled' : 'light'}
                              color="teal"
                              onClick={(e) => handleGroupSave(e, listing)}
                              leftSection={saved ? <IconBookmarkFilled size={15} /> : <IconBookmark size={15} />}
                            >
                              {saved ? 'Saved for Group' : 'Save for Group'}
                            </Button>
                          </Tooltip>
                        )}
                      </Stack>
                    </Stack>
                  </Card>
                </Grid.Col>
              );
            })}
          </Grid>
        )}
      </Container>
    </Box>
  );
}
