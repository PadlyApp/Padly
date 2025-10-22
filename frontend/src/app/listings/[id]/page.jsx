'use client';

import { Container, Title, Text, Stack, Box, Button, Group, Badge, Grid } from '@mantine/core';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Navigation } from '../../components/Navigation';
import { ImageWithFallback } from '../../components/ImageWithFallback';
import { api } from '../../../../lib/api';
import Link from 'next/link';

export default function ListingDetailPage() {
  const params = useParams();
  const listingId = params.id;

  const { data: listingData, isLoading, error } = useQuery({
    queryKey: ['listing', listingId],
    queryFn: () => api.getListing(listingId),
    enabled: !!listingId,
  });

  // Sample fallback data
  const sampleListing = {
    id: listingId,
    title: 'Cozy Studio in Downtown',
    description: 'A beautiful studio apartment in the heart of downtown. Perfect for students and young professionals. Close to public transportation and all amenities.',
    number_of_bedrooms: 1,
    number_of_bathrooms: 1,
    area_sqft: 750,
    price_per_month: 1200,
    city: 'San Francisco',
    property_type: 'Private Room',
    lease_type: 'Fixed Term',
    furnished: true,
    utilities_included: false,
    available_from: '2025-11-01',
    amenities: {
      wifi: true,
      laundry: true,
      parking: false,
      ac: true,
      heating: true,
    },
    images: ['https://images.unsplash.com/photo-1610123172763-1f587473048f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'],
  };

  const listing = listingData?.data || sampleListing;

  if (isLoading) {
    return (
      <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
        <Navigation />
        <Container size="xl" style={{ padding: '4rem 2rem' }}>
          <Text ta="center" size="lg" c="dimmed">Loading listing details...</Text>
        </Container>
      </Box>
    );
  }

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />
      
      <Container size="xl" style={{ padding: '4rem 2rem' }}>
        {/* Back Button */}
        <Link href="/matches" style={{ textDecoration: 'none' }}>
          <Button variant="subtle" color="gray" mb="xl">
            ← Back to Matches
          </Button>
        </Link>

        <Grid gutter="xl">
          {/* Images Section */}
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Box style={{ borderRadius: '1rem', overflow: 'hidden', border: '1px solid #f1f1f1' }}>
              <ImageWithFallback
                src={listing.images?.[0] || 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'}
                alt={listing.title}
                style={{ width: '100%', height: '500px', objectFit: 'cover' }}
              />
            </Box>
          </Grid.Col>

          {/* Details Section */}
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Stack gap="lg">
              <Title order={1} style={{ color: '#111', fontSize: '2rem' }}>
                {listing.title}
              </Title>

              <Text size="xl" fw={600} style={{ color: '#20c997' }}>
                ${listing.price_per_month?.toLocaleString()}/month
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
                  {listing.amenities && Object.entries(listing.amenities).map(([key, value]) => (
                    value && (
                      <Badge key={key} size="md" variant="outline" color="gray">
                        {key}
                      </Badge>
                    )
                  ))}
                </Group>
              </Stack>

              <Button
                fullWidth
                size="lg"
                radius="md"
                style={{
                  backgroundColor: '#20c997',
                  marginTop: '1rem',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#12b886';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#20c997';
                }}
              >
                Contact Host
              </Button>
            </Stack>
          </Grid.Col>
        </Grid>
      </Container>
    </Box>
  );
}

