'use client';

import { useState, useEffect, useRef } from 'react';
import { Container, Title, Text, Stack, Box, Button, Group, Badge, Grid, Tooltip, ActionIcon } from '@mantine/core';
import { SkeletonListingDetail } from '../../components/Skeletons';
import { IconBookmark, IconBookmarkFilled, IconMapPin, IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Navigation } from '../../components/Navigation';
import { ImageWithFallback } from '../../components/ImageWithFallback';
import { useAuth } from '../../contexts/AuthContext';
import { api } from '../../../../lib/api';
import { getErrorMessage } from '../../../../lib/errorHandling';
import { formatAmenityLabel } from '../../../../lib/formatters';
import { usePageTracking } from '../../hooks/usePageTracking';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Title-case a string while preserving numbers and hyphens. */
function toTitleCase(str) {
  if (!str) return '';
  const LOWER_WORDS = new Set(['a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'at', 'by', 'in', 'of', 'on', 'to', 'up']);
  return str
    .toLowerCase()
    .split(' ')
    .map((word, i) => {
      if (!word) return word;
      if (i > 0 && LOWER_WORDS.has(word)) return word;
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(' ');
}

/**
 * Parse a raw listing title like:
 *   "UPPER - 12 PERSICA STREET|Richmond Hill (Oak Ridges), Ontario L4E1L3"
 * into { street, location }.
 */
function parseTitle(raw) {
  if (!raw) return { street: '', location: '' };
  const pipeIdx = raw.indexOf('|');
  if (pipeIdx === -1) return { street: toTitleCase(raw.trim()), location: '' };
  const street = toTitleCase(raw.slice(0, pipeIdx).trim());
  const location = raw.slice(pipeIdx + 1).trim();
  return { street, location };
}

export default function ListingDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const listingId = params.id;
  const { getValidToken, authState } = useAuth();
  const recommendationSessionId = searchParams.get('recommendationSessionId');
  const recommendationSource = searchParams.get('source');
  const trackedPosition = searchParams.get('position');
  const parsedPosition = trackedPosition == null ? Number.NaN : Number(trackedPosition);
  const positionInFeed = Number.isFinite(parsedPosition) && parsedPosition >= 0 ? parsedPosition : null;

  usePageTracking('listing_detail', authState?.accessToken);

  const [userGroup, setUserGroup] = useState(null);
  const [isSaved, setIsSaved] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [imageIndex, setImageIndex] = useState(0);

  const viewStartRef = useRef(Date.now());
  useEffect(() => {
    if (!authState?.accessToken || !listingId) return;
    viewStartRef.current = Date.now();
    const genericSessionId =
      (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('padly_swipe_session_id')) ||
      `listing-detail-${Date.now()}`;
    const shouldTrackPassiveDwell = recommendationSource === 'matches' && Boolean(recommendationSessionId);

    return () => {
      const dwellMs = Math.max(0, Date.now() - viewStartRef.current);

      fetch(`${API_BASE}/api/interactions/listing-views`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify({
          listing_id: listingId,
          surface: 'listing_detail',
          session_id: genericSessionId,
          view_duration_ms: dwellMs,
          expanded: false,
          photos_viewed_count: 0,
        }),
        keepalive: true,
      }).catch(() => {});

      if (!shouldTrackPassiveDwell) return;

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

  const { data: listingData, isLoading, error, refetch } = useQuery({
    queryKey: ['listing', listingId],
    queryFn: () => api.getListing(listingId),
    enabled: !!listingId,
  });

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

  // Fetch user's group and whether this listing is saved to it.
  useEffect(() => {
    if (!listingId) return;
    let cancelled = false;
    (async () => {
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
        if (!cancelled) setIsSaved((savedData.saved_listing_ids || []).includes(listingId));
      } catch {
        // Group/saved state is non-critical.
      }
    })();
    return () => { cancelled = true; };
  }, [listingId, getValidToken]);

  const handleGroupSave = async () => {
    if (!userGroup || saveLoading) return;
    setSaveLoading(true);
    const wasSaved = isSaved;
    setIsSaved(!wasSaved);
    try {
      const token = await getValidToken();
      if (!token) { setIsSaved(wasSaved); return; }
      const res = await fetch(
        `${API_BASE}/api/interactions/swipes/groups/${userGroup.id}/save/${listingId}`,
        {
          method: wasSaved ? 'DELETE' : 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) {
        setIsSaved(wasSaved);
      }
    } catch {
      setIsSaved(wasSaved);
    } finally {
      setSaveLoading(false);
    }
  };

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
          <SkeletonListingDetail />
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

  const { street, location } = parseTitle(listing.title);

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />

      <Container size="xl" style={{ padding: '4rem 2rem' }}>
        <Link href="/matches" style={{ textDecoration: 'none' }}>
          <Button variant="subtle" color="gray" mb="xl">
            ← Back to Recommendations
          </Button>
        </Link>

        <Grid gutter="xl">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="sm">
              {/* Hero image with prev/next controls */}
              <Box style={{ position: 'relative', borderRadius: '1rem', overflow: 'hidden', border: '1px solid #f1f1f1' }}>
                <ImageWithFallback
                  src={
                    listing.images?.[imageIndex] ||
                    'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'
                  }
                  alt={`${street || listing.title} — photo ${imageIndex + 1}`}
                  style={{ width: '100%', height: '500px', objectFit: 'cover', display: 'block' }}
                />

                {listing.images?.length > 1 && (
                  <>
                    <Box style={{ position: 'absolute', top: '50%', left: 12, transform: 'translateY(-50%)' }}>
                      <ActionIcon
                        variant="filled"
                        color="dark"
                        radius="xl"
                        size="lg"
                        onClick={() => setImageIndex((prev) => (prev - 1 + listing.images.length) % listing.images.length)}
                        style={{ opacity: 0.85 }}
                        aria-label="Previous photo"
                      >
                        <IconChevronLeft size={18} />
                      </ActionIcon>
                    </Box>
                    <Box style={{ position: 'absolute', top: '50%', right: 12, transform: 'translateY(-50%)' }}>
                      <ActionIcon
                        variant="filled"
                        color="dark"
                        radius="xl"
                        size="lg"
                        onClick={() => setImageIndex((prev) => (prev + 1) % listing.images.length)}
                        style={{ opacity: 0.85 }}
                        aria-label="Next photo"
                      >
                        <IconChevronRight size={18} />
                      </ActionIcon>
                    </Box>
                    <Badge
                      variant="filled"
                      color="dark"
                      size="sm"
                      radius="sm"
                      style={{ position: 'absolute', bottom: 14, right: 14, fontWeight: 700 }}
                    >
                      {imageIndex + 1} / {listing.images.length}
                    </Badge>
                  </>
                )}
              </Box>

              {/* Thumbnail strip */}
              {listing.images?.length > 1 && (
                <Group
                  gap="xs"
                  wrap="nowrap"
                  style={{ overflowX: 'auto', padding: '0 2px 4px' }}
                >
                  {listing.images.map((img, idx) => (
                    <Box
                      key={idx}
                      onClick={() => setImageIndex(idx)}
                      style={{
                        minWidth: 80,
                        width: 80,
                        height: 60,
                        borderRadius: 8,
                        overflow: 'hidden',
                        cursor: 'pointer',
                        border: idx === imageIndex ? '2px solid #12b886' : '2px solid transparent',
                        boxShadow: idx === imageIndex ? '0 0 0 1px rgba(18,184,134,0.2)' : 'none',
                        backgroundColor: '#f3f4f6',
                        flexShrink: 0,
                      }}
                    >
                      <ImageWithFallback
                        src={img}
                        alt={`${street || listing.title} — thumbnail ${idx + 1}`}
                        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                      />
                    </Box>
                  ))}
                </Group>
              )}
            </Stack>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 5 }}>
            <Stack gap="lg">
              {/* Title block */}
              <Stack gap={4}>
                <Title order={1} style={{ color: '#111', fontSize: '1.75rem', lineHeight: 1.3 }}>
                  {street || listing.title}
                </Title>
                {location && (
                  <Group gap={6} align="center">
                    <IconMapPin size={15} color="#868e96" style={{ flexShrink: 0 }} />
                    <Text size="sm" c="dimmed">{location}</Text>
                  </Group>
                )}
              </Stack>

              <Text size="xl" fw={700} c="teal.6">
                ${Number(listing.price_per_month || 0).toLocaleString()}/month
              </Text>

              <Group gap="md">
                {listing.number_of_bedrooms != null && (
                  <Badge size="lg" color="teal" variant="light">
                    {listing.number_of_bedrooms === 0 ? 'Studio' : `${listing.number_of_bedrooms} Bed`}
                  </Badge>
                )}
                {listing.number_of_bathrooms != null && (
                  <Badge size="lg" color="teal" variant="light">
                    {listing.number_of_bathrooms} Bath
                  </Badge>
                )}
                {listing.area_sqft && (
                  <Badge size="lg" color="teal" variant="light">
                    {Number(listing.area_sqft).toLocaleString()} sq ft
                  </Badge>
                )}
              </Group>

              {listing.description && (
                <Stack gap="xs">
                  <Title order={3} size="h4" style={{ color: '#111' }}>
                    Description
                  </Title>
                  <Text c="dimmed" style={{ lineHeight: 1.6 }}>
                    {listing.description}
                  </Text>
                </Stack>
              )}

              <Stack gap="xs">
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

              {listing.amenities && Object.values(listing.amenities).some(Boolean) && (
                <Stack gap="xs">
                  <Title order={3} size="h4" style={{ color: '#111' }}>
                    Amenities
                  </Title>
                  <Group gap="sm">
                    {Object.entries(listing.amenities).map(([key, value]) =>
                      value ? (
                        <Badge key={key} size="md" variant="outline" color="gray">
                          {formatAmenityLabel(key)}
                        </Badge>
                      ) : null
                    )}
                  </Group>
                </Stack>
              )}

              <Stack gap="sm" mt="md">
                {userGroup && (
                  <Tooltip
                    label={isSaved ? `Remove from ${userGroup.group_name}` : `Save to ${userGroup.group_name}`}
                    withArrow
                  >
                    <Button
                      fullWidth
                      size="lg"
                      radius="md"
                      variant={isSaved ? 'filled' : 'light'}
                      color="teal"
                      loading={saveLoading}
                      onClick={handleGroupSave}
                      leftSection={isSaved ? <IconBookmarkFilled size={18} /> : <IconBookmark size={18} />}
                    >
                      {isSaved ? 'Saved for Group' : 'Save for Group'}
                    </Button>
                  </Tooltip>
                )}
                <Button fullWidth size="lg" radius="md" color="teal" variant="outline">
                  Contact Host
                </Button>
              </Stack>
            </Stack>
          </Grid.Col>
        </Grid>
      </Container>
    </Box>
  );
}
