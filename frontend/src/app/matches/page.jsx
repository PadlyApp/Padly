'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

import { useState, useEffect, useCallback } from 'react';
import { Container, Title, Text, Grid, Card, Badge, Button, Stack, Box, ThemeIcon, ActionIcon, Tooltip } from '@mantine/core';
import { IconSparkles, IconStar, IconStarFilled } from '@tabler/icons-react';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { useAuth } from '../contexts/AuthContext';
import { getLikedListings } from '../discover/likedListings';

export default function MatchesPage() {
  return (
    <ProtectedRoute>
      <MatchesPageContent />
    </ProtectedRoute>
  );
}

function MatchesPageContent() {
  const router = useRouter();
  const { user, authState } = useAuth();
  const userId = user?.profile?.id;

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [userGroup, setUserGroup] = useState(null);
  const [savedListingIds, setSavedListingIds] = useState(new Set());

  const fetchMatches = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      let prefs = {};
      let behaviorSampleSize;
      const liked = getLikedListings();
      const likedExtras = {};

      if (userId && authState?.accessToken) {
        const prefRes = await fetch(`${API_BASE}/api/preferences/${userId}`, {
          headers: { Authorization: `Bearer ${authState.accessToken}` },
        });
        if (prefRes.ok) {
          const prefData = await prefRes.json();
          prefs = prefData.data || prefData || {};
        }

        try {
          const behaviorRes = await fetch(`${API_BASE}/api/interactions/behavior/me?days=180`, {
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
          // Behavior vector is optional.
        }
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

      if (!res.ok) throw new Error('Failed to fetch ranked matches');

      const data = await res.json();
      setListings(data.recommendations || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [userId, authState?.accessToken]);

  useEffect(() => {
    fetchMatches();
    window.addEventListener('focus', fetchMatches);
    return () => window.removeEventListener('focus', fetchMatches);
  }, [fetchMatches]);

  useEffect(() => {
    if (!authState?.accessToken) return;
    const fetchGroup = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/roommate-groups?my_groups=true&limit=1`, {
          headers: { Authorization: `Bearer ${authState.accessToken}` },
        });
        const data = await res.json();
        console.log('[matches] groups response:', data);
        const group = data.data?.[0] || null;
        if (!group) { console.log('[matches] no group found'); return; }
        setUserGroup(group);
        console.log('[matches] userGroup set:', group.id, group.group_name);

        const savedRes = await fetch(
          `${API_BASE}/api/interactions/swipes/groups/${group.id}/saved`,
          { headers: { Authorization: `Bearer ${authState.accessToken}` } }
        );
        const savedData = await savedRes.json();
        console.log('[matches] saved listings response:', savedData);
        setSavedListingIds(new Set(savedData.saved_listing_ids || []));
      } catch (e) { console.error('[matches] fetchGroup error:', e); }
    };
    fetchGroup();
  }, [authState?.accessToken]);

  const handleGroupSave = async (listing) => {
    if (!userGroup || !authState?.accessToken) {
      console.warn('[matches] handleGroupSave blocked — userGroup:', userGroup, 'token:', !!authState?.accessToken);
      return;
    }
    const lid = listing.listing_id || listing.id;
    const isSaved = savedListingIds.has(lid);
    console.log('[matches] saving listing', lid, 'to group', userGroup.id, '— currently saved:', isSaved);

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
          headers: { Authorization: `Bearer ${authState.accessToken}` },
        }
      );
      const result = await res.json();
      console.log('[matches] save response:', res.status, result);
      if (!res.ok) throw new Error(result.detail || 'Save failed');
    } catch (e) {
      console.error('[matches] save error:', e);
      setSavedListingIds(prev => {
        const next = new Set(prev);
        isSaved ? next.add(lid) : next.delete(lid);
        return next;
      });
    }
  };

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />

      <Container size="xl" style={{ padding: '4rem 3rem' }} data-tour="matches-content">
        <Stack align="center" gap="lg" mb={64}>
          <Title
            order={1}
            style={{ fontSize: '2.5rem', fontWeight: 500, color: '#111', textAlign: 'center' }}
          >
            Your Top Matches
          </Title>
          <Text size="lg" c="dimmed" style={{ maxWidth: '42rem', textAlign: 'center', color: '#666' }}>
            Top 100 listings ranked from your preferences and recent swipe history
          </Text>
        </Stack>

        {loading && (
          <Stack align="center" gap="lg" style={{ paddingTop: '6rem', paddingBottom: '6rem' }}>
            <Text size="md" c="dimmed">Loading your ranked matches…</Text>
          </Stack>
        )}

        {!loading && error && (
          <Stack align="center" gap="lg" style={{ paddingTop: '6rem', paddingBottom: '6rem' }}>
            <Text size="md" c="red">{error}</Text>
            <Button size="md" color="teal" onClick={fetchMatches}>
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
              <Title order={3} style={{ color: '#212529' }}>No ranked matches yet</Title>
              <Text size="md" c="dimmed" ta="center" maw={420}>
                Update your preferences or broaden a hard constraint to surface more listings.
              </Text>
            </Stack>
            <Button size="md" color="teal" onClick={() => router.push('/discover')}>
              Go To Discover
            </Button>
          </Stack>
        )}

        {!loading && !error && listings.length > 0 && (
          <Grid gutter="xl">
            {listings.map((listing) => {
              const image =
                listing.images?.[0] ||
                'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080';

              return (
                <Grid.Col key={listing.listing_id} span={{ base: 12, sm: 6, lg: 4 }}>
                  <Card
                    className="card-lift"
                    shadow="sm"
                    radius="lg"
                    style={{
                      overflow: 'hidden',
                      border: '1px solid #f1f3f5',
                      cursor: 'pointer',
                    }}
                  >
                    <Card.Section style={{ position: 'relative' }}>
                      <Box style={{ position: 'relative', paddingBottom: '75%', overflow: 'hidden', backgroundColor: '#f5f5f5' }}>
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
                          style={{ position: 'absolute', top: 12, right: 12 }}
                        >
                          {listing.match_percent} match
                        </Badge>
                      )}
                    </Card.Section>

                    <Stack gap="md" style={{ padding: '1.5rem', minHeight: '220px', display: 'flex', flexDirection: 'column' }}>
                      <Text
                        fw={500}
                        size="lg"
                        style={{
                          color: '#111', lineHeight: 1.4,
                          minHeight: '56px', maxHeight: '56px', overflow: 'hidden',
                          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                        }}
                        title={listing.title}
                      >
                        {listing.title}
                      </Text>

                      <Text size="md" c="dimmed" style={{ color: '#666', minHeight: '24px' }}>
                        {[
                          listing.number_of_bedrooms != null && (listing.number_of_bedrooms === 0 ? 'Studio' : `${listing.number_of_bedrooms} Bed`),
                          listing.number_of_bathrooms != null && `${listing.number_of_bathrooms} Bath`,
                          listing.area_sqft && `${listing.area_sqft} sq ft`,
                        ].filter(Boolean).join(' • ')}
                      </Text>

                      {listing.price_per_month && (
                        <Text fw={600} size="xl" c="teal.6" style={{ minHeight: '32px' }}>
                          ${Number(listing.price_per_month).toLocaleString()}/mo
                        </Text>
                      )}

                      <Box style={{ flex: 1 }} />

                      <Stack gap="xs">
                        <Button
                          fullWidth
                          radius="md"
                          size="md"
                          color="teal"
                          onClick={() => router.push(`/listings/${listing.listing_id}`)}
                        >
                          View Details
                        </Button>
                        {userGroup && (() => {
                          const lid = listing.listing_id || listing.id;
                          const saved = savedListingIds.has(lid);
                          return (
                            <Tooltip label={saved ? 'Remove from group' : `Save to ${userGroup.group_name}`} withArrow>
                              <Button
                                fullWidth
                                radius="md"
                                size="md"
                                variant={saved ? 'filled' : 'light'}
                                onClick={() => handleGroupSave(listing)}
                                leftSection={saved ? <IconStarFilled size={16} /> : <IconStar size={16} />}
                                style={{
                                  backgroundColor: saved ? '#f59f00' : undefined,
                                  borderColor: '#ffe066',
                                  color: saved ? '#fff' : '#f59f00',
                                }}
                              >
                                {saved ? 'Saved to Group' : 'Save to Group'}
                              </Button>
                            </Tooltip>
                          );
                        })()}
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
