'use client';

import {
  Container,
  Title,
  Text,
  Grid,
  Card,
  Badge,
  Button,
  Stack,
  Box,
  ThemeIcon,
  Group,
} from '@mantine/core';
import { SkeletonListingCard } from '../../../app/components/Skeletons';
import { IconSparkles, IconMapPin, IconRefresh } from '@tabler/icons-react';
import { Navigation } from '../../../app/components/Navigation';
import { ImageWithFallback } from '../../../app/components/ImageWithFallback';
import { formatAmenityLabel, getActiveAmenityKeys } from '../../../../lib/formatters';
import {
  MATCHES_FEEDBACK_CHOICES,
  MATCHES_NEGATIVE_REASON_CHOICES,
} from '../../../../lib/recommendationFeedback';
import { parseListingTitle } from '../lib/parseListingTitle';

export function MatchesPageView(props) {
  const {
    router,
    feedbackAcknowledged,
    hasStaleChanges,
    handleReloadMatches,
    loading,
    error,
    listings,
    retrySecondsLeft,
    handleRetry,
    missingCorePreferences,
    showFeedbackPrompt,
    feedbackStep,
    feedbackSubmitting,
    handleFeedbackChoice,
    dismissFeedbackPrompt,
    handleNegativeReason,
    submitFeedback,
    pendingFeedbackLabel,
    targetStateFallback,
    handleViewDetails,
  } = props;

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
          {feedbackAcknowledged && (
            <Text size="sm" c="teal.7">
              Thanks. Your feedback was saved for recommendation evaluation.
            </Text>
          )}
          {hasStaleChanges && !loading && (
            <Button
              variant="light"
              color="teal"
              size="sm"
              leftSection={<IconRefresh size={15} />}
              onClick={handleReloadMatches}
            >
              Your preferences or likes have changed — Reload Matches
            </Button>
          )}
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
            <Button
              size="md"
              color="teal"
              onClick={handleRetry}
              disabled={retrySecondsLeft > 0}
            >
              {retrySecondsLeft > 0 ? `Retry in ${retrySecondsLeft}s` : 'Retry'}
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
          <Stack gap="xl">
            {showFeedbackPrompt && (
              <Card
                shadow="sm"
                radius="lg"
                style={{
                  position: 'sticky',
                  top: '5.5rem',
                  zIndex: 10,
                  border: '1px solid #d3f9d8',
                  backgroundColor: '#f8fff9',
                }}
              >
                <Stack gap="md">
                  {feedbackStep === 'question' ? (
                    <>
                      <Stack gap={4}>
                        <Title order={4} style={{ color: '#111' }}>
                          How useful were these recommendations?
                        </Title>
                        <Text size="sm" c="dimmed">
                          Your feedback helps us improve how listings are ranked.
                        </Text>
                      </Stack>
                      <Stack gap="sm">
                        {MATCHES_FEEDBACK_CHOICES.map((choice) => (
                          <Button
                            key={choice.value}
                            size="md"
                            variant={choice.value === 'very_useful' ? 'filled' : 'light'}
                            color="teal"
                            disabled={feedbackSubmitting}
                            onClick={() => handleFeedbackChoice(choice.value)}
                          >
                            {choice.label}
                          </Button>
                        ))}
                        <Button
                          size="sm"
                          variant="subtle"
                          color="gray"
                          disabled={feedbackSubmitting}
                          onClick={dismissFeedbackPrompt}
                        >
                          Not now
                        </Button>
                      </Stack>
                    </>
                  ) : (
                    <>
                      <Stack gap={4}>
                        <Title order={4} style={{ color: '#111' }}>
                          What felt off?
                        </Title>
                        <Text size="sm" c="dimmed">
                          Optional
                        </Text>
                      </Stack>
                      <Stack gap="sm">
                        {MATCHES_NEGATIVE_REASON_CHOICES.map((choice) => (
                          <Button
                            key={choice.value}
                            size="md"
                            variant="light"
                            color="teal"
                            disabled={feedbackSubmitting}
                            onClick={() => handleNegativeReason(choice.value)}
                          >
                            {choice.label}
                          </Button>
                        ))}
                        <Button
                          size="sm"
                          variant="subtle"
                          color="gray"
                          disabled={feedbackSubmitting}
                          onClick={() => submitFeedback({ feedbackLabel: pendingFeedbackLabel || 'not_useful' })}
                        >
                          Skip
                        </Button>
                      </Stack>
                    </>
                  )}
                </Stack>
              </Card>
            )}

            <Grid gutter="lg">
              {listings.map((listing) => {
                const image =
                  listing.images?.[0] ||
                  'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080';

                const { street, location } = parseListingTitle(listing.title);
                const cityState = [listing.city, listing.state_province || listing.state || targetStateFallback]
                  .filter(Boolean)
                  .join(', ');
                const locationText = cityState || location;
                const amenityBadges = getActiveAmenityKeys(listing.amenities).slice(0, 2);

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
                      onClick={() => handleViewDetails(listing)}
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
                          {locationText && (
                            <Group gap={4} mt={8} mb={2}>
                              <IconMapPin size={12} color="#868e96" style={{ flexShrink: 0 }} />
                              <Text size="sm" fw={500} c="dimmed" lineClamp={1} style={{ flex: 1 }}>
                                {locationText}
                              </Text>
                            </Group>
                          )}
                        </Box>

                        <Text size="sm" c="dimmed">
                          {[
                            listing.number_of_bedrooms != null && (listing.number_of_bedrooms === 0 ? 'Studio' : `${listing.number_of_bedrooms} Bed`),
                            listing.number_of_bathrooms != null && `${listing.number_of_bathrooms} Bath`,
                            listing.area_sqft && `${Number(listing.area_sqft).toLocaleString()} sq ft`,
                          ].filter(Boolean).join(' · ')}
                        </Text>

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

                        {listing.price_per_month && (
                          <Text fw={700} size="xl" c="teal.6" style={{ marginTop: 'auto', paddingTop: '0.5rem' }}>
                            ${Number(listing.price_per_month).toLocaleString()}/mo
                          </Text>
                        )}

                        <Stack gap="xs" mt="xs">
                          <Button
                            fullWidth
                            radius="md"
                            size="sm"
                            color="teal"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleViewDetails(listing);
                            }}
                          >
                            View Details
                          </Button>
                        </Stack>
                      </Stack>
                    </Card>
                  </Grid.Col>
                );
              })}
            </Grid>
          </Stack>
        )}
      </Container>
    </Box>
  );
}

