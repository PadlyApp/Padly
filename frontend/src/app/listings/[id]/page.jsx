'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

import { Container, Title, Text, Stack, Box, Button, Group, Badge, Grid } from '@mantine/core';
import { useEffect, useMemo, useRef } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Navigation } from '../../components/Navigation';
import { ImageWithFallback } from '../../components/ImageWithFallback';
import { api } from '../../../../lib/api';
import { getErrorMessage } from '../../../../lib/errorHandling';
import Link from 'next/link';
import { useAuth } from '../../contexts/AuthContext';
import { createRecommendationEventId } from '../../../../lib/recommendationFeedback';

export default function ListingDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const { authState } = useAuth();
  const listingId = params.id;
  const detailStartedAtRef = useRef(Date.now());
  const recommendationSessionId = searchParams.get('recommendationSessionId');
  const recommendationSource = searchParams.get('source');
  const trackedPosition = searchParams.get('position');
  const positionInFeed = useMemo(() => {
    if (trackedPosition == null) return null;
    const parsed = Number(trackedPosition);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
  }, [trackedPosition]);

  const { data: listingData, isLoading, error, refetch } = useQuery({
    queryKey: ['listing', listingId],
    queryFn: () => api.getListing(listingId),
    enabled: !!listingId,
  });

  useEffect(() => {
    detailStartedAtRef.current = Date.now();
  }, [listingId]);

  useEffect(() => {
    const shouldTrackPassiveDwell =
      recommendationSource === 'matches'
      && !!recommendationSessionId
      && !!authState?.accessToken
      && !!listingId;

    return () => {
      if (!shouldTrackPassiveDwell) return;

      const dwellMs = Math.max(0, Date.now() - detailStartedAtRef.current);
      fetch(`${API_BASE}/api/interactions/recommendation-events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify({
          recommendation_session_id: recommendationSessionId,
          client_event_id: createRecommendationEventId('detail-view'),
          surface: 'matches',
          event_type: 'detail_view',
          listing_id: listingId,
          position_in_feed: positionInFeed,
          dwell_ms: dwellMs,
          metadata: {
            source: 'listing_detail_page',
          },
        }),
        keepalive: true,
      }).catch(() => {});
    };
  }, [authState?.accessToken, listingId, positionInFeed, recommendationSessionId, recommendationSource]);

  const rawListing = listingData?.data || null;
  const parsedImages = (() => {
    const imgs = rawListing?.images;
    if (Array.isArray(imgs)) return imgs;
    if (typeof imgs === 'string') {
      try {
        return JSON.parse(imgs);
      } catch {
        return [];
      }
    }
    return [];
  })();
  const listing = rawListing ? { ...rawListing, images: parsedImages } : null;

  const isNotFound = error?.status === 404;
  const errorMessage = getErrorMessage(
    error,
    isNotFound ? 'Listing not found.' : 'Could not load this listing right now.'
  );

  if (isLoading) {
    return (
      <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
        <Navigation />
        <Container size="xl" style={{ padding: '4rem 2rem' }}>
          <Text ta="center" size="lg" c="dimmed">
            Loading listing details...
          </Text>
        </Container>
      </Box>
    );
  }

  if (error || !listing) {
    return (
      <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
        <Navigation />
        <Container size="md" style={{ padding: '4rem 2rem' }}>
          <Stack align="center" gap="lg" py="xl">
            <Title order={2} ta="center">
              {isNotFound ? 'This listing is unavailable' : 'Unable to load listing'}
            </Title>
            <Text c="dimmed" ta="center" maw={480}>
              {isNotFound
                ? 'This listing may have been removed or is no longer active.'
                : errorMessage}
            </Text>
            <Group>
              {!isNotFound && (
                <Button color="teal" onClick={() => refetch()}>
                  Try again
                </Button>
              )}
              <Button variant="light" color="teal" component={Link} href="/matches">
                Back to Matches
              </Button>
            </Group>
          </Stack>
        </Container>
      </Box>
    );
  }

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />

      <Container size="xl" style={{ padding: '4rem 2rem' }}>
        <Link href="/matches" style={{ textDecoration: 'none' }}>
          <Button variant="subtle" color="gray" mb="xl">
            {'<'}- Back to Matches
          </Button>
        </Link>

        <Grid gutter="xl">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Box style={{ borderRadius: '1rem', overflow: 'hidden', border: '1px solid #f1f1f1' }}>
              <ImageWithFallback
                src={
                  listing.images?.[0] ||
                  'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'
                }
                alt={listing.title}
                style={{ width: '100%', height: '500px', objectFit: 'cover' }}
              />
            </Box>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 5 }}>
            <Stack gap="lg">
              <Title order={1} style={{ color: '#111', fontSize: '2rem' }}>
                {listing.title}
              </Title>

              <Text size="xl" fw={600} c="teal.6">
                ${Number(listing.price_per_month || 0).toLocaleString()}/month
              </Text>

              <Group gap="md">
                <Badge size="lg" color="teal" variant="light">
                  {listing.number_of_bedrooms} Bed
                </Badge>
                <Badge size="lg" color="teal" variant="light">
                  {listing.number_of_bathrooms} Bath
                </Badge>
                <Badge size="lg" color="teal" variant="light">
                  {listing.area_sqft} sq ft
                </Badge>
              </Group>

              <Stack gap="sm">
                <Title order={3} size="h4" style={{ color: '#111' }}>
                  Description
                </Title>
                <Text c="dimmed" style={{ color: '#666', lineHeight: 1.6 }}>
                  {listing.description}
                </Text>
              </Stack>

              <Stack gap="sm">
                <Title order={3} size="h4" style={{ color: '#111' }}>
                  Details
                </Title>
                <Stack gap="xs">
                  <Group justify="space-between">
                    <Text c="dimmed">Property Type:</Text>
                    <Text fw={500}>{listing.property_type || 'N/A'}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text c="dimmed">Lease Type:</Text>
                    <Text fw={500}>{listing.lease_type || 'N/A'}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text c="dimmed">Furnished:</Text>
                    <Text fw={500}>{listing.furnished ? 'Yes' : 'No'}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text c="dimmed">Utilities Included:</Text>
                    <Text fw={500}>{listing.utilities_included ? 'Yes' : 'No'}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text c="dimmed">Available From:</Text>
                    <Text fw={500}>{listing.available_from || 'Immediate'}</Text>
                  </Group>
                </Stack>
              </Stack>

              <Stack gap="sm">
                <Title order={3} size="h4" style={{ color: '#111' }}>
                  Amenities
                </Title>
                <Group gap="sm">
                  {listing.amenities &&
                    Object.entries(listing.amenities).map(([key, value]) =>
                      value ? (
                        <Badge key={key} size="md" variant="outline" color="gray">
                          {key}
                        </Badge>
                      ) : null
                    )}
                </Group>
              </Stack>

              <Button fullWidth size="lg" radius="md" color="teal" mt="md">
                Contact Host
              </Button>
            </Stack>
          </Grid.Col>
        </Grid>
      </Container>
    </Box>
  );
}
