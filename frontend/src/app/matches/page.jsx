'use client';

import { Container, Title, Text, Grid, Card, Badge, Button, Group, Stack, Box } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { api } from '../../../lib/api';

// Mock data for demonstration - this calculates match scores based on preferences
const calculateMatchScore = (listing) => {
  // This is a simplified match score calculation
  // In production, this would be done on the backend based on user preferences
  // Using deterministic calculation to avoid hydration mismatch
  const hash = listing.id.split('').reduce((acc, char) => {
    return acc + char.charCodeAt(0);
  }, 0);
  return 85 + (hash % 15); // Score between 85-99
};

export default function MatchesPage() {
  const router = useRouter();
  
  const { data: listingsData, isLoading, error } = useQuery({
    queryKey: ['listings'],
    queryFn: api.getListings,
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Sample fallback data if API fails
  const sampleListings = [
    {
      id: '1',
      title: 'Cozy Studio in Downtown',
      number_of_bedrooms: 1,
      number_of_bathrooms: 1,
      area_sqft: 750,
      price_per_month: 1200,
      city: 'San Francisco',
      images: ['https://images.unsplash.com/photo-1610123172763-1f587473048f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'],
    },
    {
      id: '2',
      title: 'Modern Loft with City Views',
      number_of_bedrooms: 2,
      number_of_bathrooms: 2,
      area_sqft: 1200,
      price_per_month: 2400,
      city: 'Seattle',
      images: ['https://images.unsplash.com/photo-1603072388139-565853396b38?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'],
    },
    {
      id: '3',
      title: 'Bright Corner Unit',
      number_of_bedrooms: 1,
      number_of_bathrooms: 1,
      area_sqft: 850,
      price_per_month: 1500,
      city: 'Austin',
      images: ['https://images.unsplash.com/photo-1632077209523-e9dede9b6b31?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'],
    },
    {
      id: '4',
      title: 'Minimalist Suite',
      number_of_bedrooms: 1,
      number_of_bathrooms: 1,
      area_sqft: 680,
      price_per_month: 1100,
      city: 'Portland',
      images: ['https://images.unsplash.com/photo-1614622350812-96b09c78af77?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'],
    },
    {
      id: '5',
      title: 'Urban Living Space',
      number_of_bedrooms: 2,
      number_of_bathrooms: 1,
      area_sqft: 950,
      price_per_month: 1800,
      city: 'Denver',
      images: ['https://images.unsplash.com/photo-1552189864-e05b02af1697?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'],
    },
    {
      id: '6',
      title: 'Spacious Industrial Loft',
      number_of_bedrooms: 3,
      number_of_bathrooms: 2,
      area_sqft: 1500,
      price_per_month: 2800,
      city: 'Boston',
      images: ['https://images.unsplash.com/photo-1681684565407-01d2933ed16f?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080'],
    },
  ];

  // Use API data if available, otherwise use sample data
  // Only use sample data if there's an error or no data from API
  const listings = (listingsData?.data?.listings && listingsData.data.listings.length > 0) 
    ? listingsData.data.listings 
    : sampleListings;

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#ffffff' }}>
      <Navigation />
      
      <Container size="xl" style={{ padding: '4rem 3rem' }}>
        {/* Header Section */}
        <Stack align="center" gap="lg" mb={64}>
          <Title 
            order={1} 
            style={{ 
              fontSize: '2.5rem', 
              fontWeight: 500,
              color: '#111',
              textAlign: 'center'
            }}
          >
            Your perfect place awaits
          </Title>
          <Text 
            size="lg" 
            c="dimmed" 
            style={{ 
              maxWidth: '42rem', 
              textAlign: 'center',
              color: '#666'
            }}
          >
            Here are your top matches based on your preferences
          </Text>
        </Stack>

        {/* Loading State */}
        {isLoading && (
          <Text ta="center" size="lg" c="dimmed">
            Loading your perfect matches...
          </Text>
        )}

        {/* Error State */}
        {error && (
          <Text ta="center" size="lg" c="orange" mb="xl">
            ⚠️ Backend not connected. Showing sample data.
          </Text>
        )}

        {/* Listings Grid */}
        <Grid gutter="xl">
          {listings.map((listing) => {
            const matchScore = calculateMatchScore(listing);
            const image = listing.images?.[0] || listing.image || 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080';
            
            return (
              <Grid.Col key={listing.id} span={{ base: 12, sm: 6, lg: 4 }}>
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
                    e.currentTarget.style.boxShadow = '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow = '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)';
                  }}
                >
                  {/* Image Section */}
                  <Card.Section style={{ position: 'relative' }}>
                    <Box style={{ position: 'relative', paddingBottom: '75%', overflow: 'hidden', backgroundColor: '#f5f5f5' }}>
                      <ImageWithFallback
                        src={image}
                        alt={listing.title}
                        style={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          width: '100%',
                          height: '100%',
                          objectFit: 'cover',
                          transition: 'transform 0.5s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.transform = 'scale(1.05)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.transform = 'scale(1)';
                        }}
                      />
                    </Box>
                    
                    {/* Match Score Badge */}
                    <Badge
                      size="lg"
                      radius="md"
                      style={{
                        position: 'absolute',
                        top: '1rem',
                        right: '1rem',
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        color: '#20c997',
                        backdropFilter: 'blur(8px)',
                        border: 'none',
                        boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
                      }}
                    >
                      Match: {matchScore}%
                    </Badge>
                  </Card.Section>

                  {/* Content Section */}
                  <Stack gap="md" style={{ padding: '1.5rem', minHeight: '220px', display: 'flex', flexDirection: 'column' }}>
                    {/* Title - Fixed height with ellipsis */}
                    <Text 
                      fw={500} 
                      size="lg"
                      style={{ 
                        color: '#111',
                        lineHeight: 1.4,
                        minHeight: '56px',
                        maxHeight: '56px',
                        overflow: 'hidden',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}
                      title={listing.title}
                    >
                      {listing.title}
                    </Text>

                    {/* Details - Single line */}
                    <Text 
                      size="md" 
                      c="dimmed"
                      style={{ color: '#666', minHeight: '24px' }}
                    >
                      {listing.number_of_bedrooms || listing.beds} Bed • {listing.number_of_bathrooms || listing.baths} Bath • {listing.area_sqft || listing.sqft} sq ft
                    </Text>

                    {/* Price - Fixed height */}
                    {listing.price_per_month && (
                      <Text 
                        fw={600} 
                        size="xl"
                        style={{ color: '#20c997', minHeight: '32px' }}
                      >
                        ${listing.price_per_month.toLocaleString()}/mo
                      </Text>
                    )}

                    {/* Spacer to push button to bottom */}
                    <Box style={{ flex: 1 }} />

                    {/* View Details Button */}
                    <Button
                      fullWidth
                      radius="md"
                      size="md"
                      style={{
                        backgroundColor: '#20c997',
                        transition: 'background-color 0.2s ease',
                      }}
                      onClick={() => router.push(`/listings/${listing.id}`)}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#12b886';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#20c997';
                      }}
                    >
                      View Details
                    </Button>
                  </Stack>
                </Card>
              </Grid.Col>
            );
          })}
        </Grid>
      </Container>
    </Box>
  );
}

