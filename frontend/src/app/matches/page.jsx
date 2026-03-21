'use client';

import { useState, useEffect } from 'react';
import { Container, Title, Text, Grid, Card, Badge, Button, Group, Stack, Box } from '@mantine/core';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { getLikedListings } from '../discover/page';

export default function MatchesPage() {
  return (
    <ProtectedRoute>
      <MatchesPageContent />
    </ProtectedRoute>
  );
}

function MatchesPageContent() {
  const router = useRouter();
  const [listings, setListings] = useState([]);

  // Read from localStorage on mount (and whenever the page gains focus)
  const loadLiked = () => setListings(getLikedListings());

  useEffect(() => {
    loadLiked();
    window.addEventListener('focus', loadLiked);
    return () => window.removeEventListener('focus', loadLiked);
  }, []);

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />

      <Container size="xl" style={{ padding: '4rem 3rem' }}>
        {/* Header */}
        <Stack align="center" gap="lg" mb={64}>
          <Title
            order={1}
            style={{ fontSize: '2.5rem', fontWeight: 500, color: '#111', textAlign: 'center' }}
          >
            Your Matches
          </Title>
          <Text size="lg" c="dimmed" style={{ maxWidth: '42rem', textAlign: 'center', color: '#666' }}>
            Listings you've liked while browsing Discover
          </Text>
        </Stack>

        {/* Empty state */}
        {listings.length === 0 && (
          <Stack align="center" gap="lg" mt={64}>
            <Text style={{ fontSize: '3rem' }}>💚</Text>
            <Title order={3} style={{ color: '#111' }}>No matches yet</Title>
            <Text size="lg" c="dimmed" ta="center" maw={400}>
              Head over to Discover and swipe right on listings you like — they'll show up here.
            </Text>
            <Button
              size="lg"
              style={{ backgroundColor: '#20c997' }}
              onClick={() => router.push('/discover')}
            >
              Start Discovering
            </Button>
          </Stack>
        )}

        {/* Listings grid */}
        {listings.length > 0 && (
          <Grid gutter="xl">
            {listings.map((listing) => {
              const image =
                listing.images?.[0] ||
                'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080';

              return (
                <Grid.Col key={listing.listing_id} span={{ base: 12, sm: 6, lg: 4 }}>
                  <Card
                    shadow="sm"
                    radius="lg"
                    style={{
                      overflow: 'hidden',
                      border: '1px solid #f1f1f1',
                      transition: 'all 0.3s ease',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.boxShadow =
                        '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.boxShadow =
                        '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)';
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
                            transition: 'transform 0.5s ease',
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.05)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
                        />
                      </Box>
                      {listing.match_percent && (
                        <Badge
                          style={{
                            position: 'absolute', top: 12, right: 12,
                            backgroundColor: '#20c997', color: '#fff',
                          }}
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
                          listing.number_of_bedrooms != null && `${listing.number_of_bedrooms} Bed`,
                          listing.number_of_bathrooms != null && `${listing.number_of_bathrooms} Bath`,
                          listing.area_sqft && `${listing.area_sqft} sq ft`,
                        ].filter(Boolean).join(' • ')}
                      </Text>

                      {listing.price_per_month && (
                        <Text fw={600} size="xl" style={{ color: '#20c997', minHeight: '32px' }}>
                          ${Number(listing.price_per_month).toLocaleString()}/mo
                        </Text>
                      )}

                      <Box style={{ flex: 1 }} />

                      <Button
                        fullWidth
                        radius="md"
                        size="md"
                        style={{ backgroundColor: '#20c997', transition: 'background-color 0.2s ease' }}
                        onClick={() => router.push(`/listings/${listing.listing_id}`)}
                        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#12b886'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#20c997'; }}
                      >
                        View Details
                      </Button>
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
