'use client';

import {
  Container,
  Box,
  Text,
  Title,
  Button,
  Stack,
  ActionIcon,
  Group,
  Progress,
  Modal,
  Badge,
  Divider,
  ThemeIcon,
} from '@mantine/core';
import { IconX, IconHeart, IconRefresh, IconInfoCircle, IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import { ImageWithFallback } from '../../../app/components/ImageWithFallback';
import { Navigation } from '../../../app/components/Navigation';
import { SkeletonSwipeCard } from '../../../app/components/Skeletons';
import { SwipeCard } from '../../../app/components/SwipeCard';
import {
  MATCHES_FEEDBACK_CHOICES,
  MATCHES_NEGATIVE_REASON_CHOICES,
} from '../../../../lib/recommendationFeedback';
import { GROUPS_FEATURE_ENABLED } from '../../../../lib/featureFlags';
import { formatAmenityLabel, formatEnumLabel, getActiveAmenityKeys, parseListingTitle } from '../../../../lib/formatters';

export function DiscoverPageView(props) {
  const {
    router,
    feedbackAcknowledged,
    loading,
    isDone,
    noRecommendations,
    remaining,
    isGuest,
    guestCity,
    guestNudgeShown,
    setGuestNudgeShown,
    showFeedbackPrompt,
    feedbackStep,
    feedbackSubmitting,
    handleFeedbackChoice,
    dismissFeedbackPrompt,
    handleNegativeReason,
    submitFeedback,
    pendingFeedbackLabel,
    handleDiscoverFeedReload,
    error,
    emptyResultReason,
    missingCorePreferences,
    listings,
    currentIndex,
    handleSwipe,
    openExpanded,
    cardPhotoCountRef,
    handleButton,
    expandedListing,
    closeExpanded,
    expandedImageIndex,
    setExpandedImageIndex,
    setFullscreenOpen,
    fullscreenOpen,
    handleModalAction,
    showGuestSignupModal,
    setShowGuestSignupModal,
    setCurrentIndex,
    logGuestEvent,
    pendingGuestLike,
    setPendingGuestLike,
  } = props;

  return (
    <Box style={{ minHeight: '100vh', backgroundColor: '#fafafa' }}>
      <Navigation />

      <Container size="sm" style={{ padding: '2rem 1rem' }}>
        {/* Header */}
        <Stack align="center" gap={4} mb="xl">
          <Title order={2} style={{ color: '#111', fontWeight: 500 }}>
            Discover
          </Title>
          {feedbackAcknowledged && (
            <Text size="sm" c="teal.7">
              Thanks. Your feedback was saved for recommendation evaluation.
            </Text>
          )}
          {!loading && !isDone && !noRecommendations && (
            <Text size="sm" c="dimmed" data-tour="discover-counter">
              {remaining} listing{remaining !== 1 ? 's' : ''} left
            </Text>
          )}
          {isGuest && !guestCity && (
            <Button size="sm" color="teal" variant="light" onClick={() => router.push('/preferences-setup')}>
              Set your location to see listings
            </Button>
          )}
        </Stack>

        {/* Guest nudge banner — shown after 5 swipes */}
        {isGuest && guestNudgeShown && (
          <Box
            style={{
              border: '1px solid #96f2d7',
              background: '#f0fdf9',
              borderRadius: 12,
              padding: '0.85rem 1rem',
              marginBottom: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.75rem',
              flexWrap: 'wrap',
            }}
          >
            <Text size="sm" style={{ color: '#0ca678' }}>
              Sign up to save your liked listings and get unlimited access.
            </Text>
            <Group gap="xs">
              <Button size="xs" color="teal" onClick={() => router.push('/signup')}>
                Create free account
              </Button>
              <Button size="xs" variant="subtle" color="gray" onClick={() => setGuestNudgeShown(false)}>
                Not now
              </Button>
            </Group>
          </Box>
        )}

        {showFeedbackPrompt && (
          <Box style={{ width: '100%', maxWidth: 520, margin: '0 auto 1.25rem' }}>
            <Box
              style={{
                border: '1px solid #d3f9d8',
                backgroundColor: '#f8fff9',
                borderRadius: 16,
                padding: '1rem',
                boxShadow: '0 8px 28px rgba(18, 184, 134, 0.08)',
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
            </Box>
          </Box>
        )}

        {/* Content */}
        <Stack align="center" gap="xl">

          {/* Loading */}
          {loading && <SkeletonSwipeCard />}

          {/* Error */}
          {!loading && error && (
            <Stack align="center" gap="md" style={{ height: 520, justifyContent: 'center' }}>
              <Text c="red">{error}</Text>
              <Button onClick={handleDiscoverFeedReload} variant="light" color="teal">
                Try again
              </Button>
            </Stack>
          )}

          {/* No recommendations */}
          {noRecommendations && (
            <Stack align="center" gap="lg" style={{ height: 520, justifyContent: 'center' }}>
              <ThemeIcon size={72} radius="xl" variant="light" color="teal">
                <IconInfoCircle size={36} />
              </ThemeIcon>
              <Title order={3} style={{ color: '#111' }}>
                {emptyResultReason === 'missing_preferences'
                  ? 'Complete your preferences'
                  : 'No listings match right now'}
              </Title>
              <Text c="dimmed" ta="center" maw={420}>
                {emptyResultReason === 'missing_preferences'
                  ? 'Set your country, state/province, and city to get location-aware recommendations.'
                  : 'Try broadening one hard constraint like budget, room preference, or move-in date.'}
              </Text>
              <Group gap="md" justify="center">
                <Button
                  variant="light"
                  color="teal"
                  onClick={() => router.push('/account?tab=preferences')}
                >
                  Open Preferences
                </Button>
                <Button
                  leftSection={<IconRefresh size={16} />}
                  onClick={handleDiscoverFeedReload}
                  color="teal"
                >
                  Retry
                </Button>
              </Group>
              {missingCorePreferences && (
                <Text size="sm" c="dimmed" ta="center">
                  Listing ranking improves once your core location constraints are set.
                </Text>
              )}
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
                  onClick={handleDiscoverFeedReload}
                  color="teal"
                >
                  Reload
                </Button>
                <Button variant="light" color="teal" onClick={() => router.push('/matches')}>
                  View Matches
                </Button>
                {GROUPS_FEATURE_ENABLED && (
                  <Button variant="outline" color="teal" onClick={() => router.push('/roommates')}>
                    Find roommate matches
                  </Button>
                )}
              </Group>
            </Stack>
          )}

          {/* Card stack + buttons */}
          {!loading && !error && !isDone && !noRecommendations && (
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
                      onExpand={openExpanded}
                      onPhotoChange={offset === 0 ? () => { cardPhotoCountRef.current += 1; } : undefined}
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
        onClose={closeExpanded}
        size="min(90vw, 720px)"
        padding={0}
        radius="lg"
        centered
        overlayProps={{ backgroundOpacity: 0.5, blur: 6 }}
        transitionProps={{ transition: 'slide-up', duration: 300 }}
        withCloseButton={false}
        styles={{ body: { maxHeight: '90vh', overflowY: 'auto' } }}
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

          const { street: modalStreet, location: modalLocation } = parseListingTitle(expandedListing.title);
          const modalCity = expandedListing.city || '';
          const modalDisplayStreet = modalCity
            ? modalStreet.replace(
                new RegExp(`[,\\s–-]*${modalCity.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`, 'i'),
                ''
              ).trim() || modalStreet
            : modalStreet;
          const modalDisplayLocation = modalLocation || modalCity;

          const amenityKeys = getActiveAmenityKeys(expandedListing.amenities);

          const bedsLabel = expandedListing.number_of_bedrooms === 0
            ? 'Studio'
            : expandedListing.number_of_bedrooms != null
              ? String(expandedListing.number_of_bedrooms)
              : '—';

          return (
            <Box>
              {/* Hero image */}
              <Box style={{ position: 'relative', height: 300, overflow: 'hidden', borderRadius: '12px 12px 0 0' }}>
                <Box
                  onClick={() => setFullscreenOpen(true)}
                  style={{ width: '100%', height: '100%', cursor: 'zoom-in' }}
                >
                  <ImageWithFallback
                    src={heroImage}
                    alt={expandedListing.title || 'Listing'}
                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                  />
                </Box>

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
                    onClick={closeExpanded}
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
                    {modalDisplayStreet || 'Listing'}
                  </Text>
                  {modalDisplayLocation && (
                    <Text size="sm" style={{ color: 'rgba(255,255,255,0.80)', marginTop: 2 }}>
                      {modalDisplayLocation}
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
                      key={`${expandedListing.listing_id || 'listing'}-${index}`}
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
                        alt={`${modalDisplayStreet || 'Listing'} ${index + 1}`}
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
                      {formatEnumLabel(expandedListing.property_type)}
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
                      <Text size="sm">{formatEnumLabel(expandedListing.lease_type)}</Text>
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
                {amenityKeys.length > 0 && (
                  <Group gap="xs" mb="md" wrap="wrap">
                    {amenityKeys.map((key) => (
                        <Badge key={key} variant="light" color="teal" size="sm" radius="sm">
                          {formatAmenityLabel(key)}
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

      {/* Fullscreen image viewer */}
      {expandedListing && fullscreenOpen && (() => {
        const imgs = (() => {
          const i = expandedListing?.images;
          if (Array.isArray(i)) return i;
          if (typeof i === 'string') { try { return JSON.parse(i); } catch { return []; } }
          return [];
        })();
        const safeIdx = imgs.length > 0 ? Math.min(expandedImageIndex, imgs.length - 1) : 0;
        return (
          <Modal
            opened={fullscreenOpen}
            onClose={() => setFullscreenOpen(false)}
            size="min(92vw, 900px)"
            padding={0}
            radius="xl"
            withCloseButton={false}
            centered
            overlayProps={{ backgroundOpacity: 0.75, blur: 10 }}
            transitionProps={{ transition: 'fade', duration: 200 }}
            styles={{
              body: { backgroundColor: '#111', borderRadius: 'var(--mantine-radius-xl)' },
              content: { backgroundColor: '#111', borderRadius: 'var(--mantine-radius-xl)' },
            }}
          >
            <Box style={{ position: 'relative', width: '100%', aspectRatio: '16/10', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--mantine-radius-xl)', overflow: 'hidden' }}>
              <ImageWithFallback
                src={imgs[safeIdx]}
                alt={`Image ${safeIdx + 1}`}
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />

              {/* Close */}
              <ActionIcon
                variant="filled"
                color="dark"
                size="lg"
                radius="xl"
                onClick={() => setFullscreenOpen(false)}
                style={{ position: 'absolute', top: 16, right: 16, opacity: 0.85 }}
              >
                <IconX size={18} />
              </ActionIcon>

              {/* Counter */}
              {imgs.length > 1 && (
                <Badge
                  variant="filled"
                  color="dark"
                  size="sm"
                  radius="sm"
                  style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)' }}
                >
                  {safeIdx + 1} / {imgs.length}
                </Badge>
              )}

              {/* Prev */}
              {imgs.length > 1 && (
                <ActionIcon
                  variant="filled"
                  color="dark"
                  radius="xl"
                  size="lg"
                  onClick={() => setExpandedImageIndex((prev) => (prev - 1 + imgs.length) % imgs.length)}
                  style={{ position: 'absolute', top: '50%', left: 16, transform: 'translateY(-50%)', opacity: 0.85 }}
                >
                  <IconChevronLeft size={18} />
                </ActionIcon>
              )}

              {/* Next */}
              {imgs.length > 1 && (
                <ActionIcon
                  variant="filled"
                  color="dark"
                  radius="xl"
                  size="lg"
                  onClick={() => setExpandedImageIndex((prev) => (prev + 1) % imgs.length)}
                  style={{ position: 'absolute', top: '50%', right: 16, transform: 'translateY(-50%)', opacity: 0.85 }}
                >
                  <IconChevronRight size={18} />
                </ActionIcon>
              )}
            </Box>
          </Modal>
        );
      })()}

      {/* Guest signup modal — shown when a guest tries to like a listing */}
      <Modal
        opened={showGuestSignupModal}
        onClose={() => {
          setShowGuestSignupModal(false);
          // Advance past the card the guest tried to like so they can keep browsing
          setCurrentIndex(prev => prev + 1);
          void logGuestEvent({ event_type: 'signup_prompt_dismissed', listing_id: pendingGuestLike?.listing_id ?? null });
          setPendingGuestLike(null);
        }}
        size="sm"
        radius="lg"
        centered
        padding="xl"
        title={null}
        overlayProps={{ backgroundOpacity: 0.5, blur: 4 }}
        withCloseButton={false}
      >
        <Stack gap="lg" align="center" ta="center">
          <Box style={{ fontSize: '2.5rem' }}>🏠</Box>
          <Stack gap={4}>
            <Title order={3} style={{ color: '#111' }}>Save this listing</Title>
            <Text size="sm" c="dimmed">
              Create a free account to like listings, see your matches, and get unlimited access.
            </Text>
          </Stack>
          <Stack gap="sm" style={{ width: '100%' }}>
            <Button
              color="teal"
              size="md"
              fullWidth
              onClick={() => {
                void logGuestEvent({ event_type: 'signup_prompt_clicked', listing_id: pendingGuestLike?.listing_id ?? null });
                router.push('/signup');
              }}
            >
              Create free account
            </Button>
            <Button
              variant="subtle"
              color="gray"
              size="sm"
              fullWidth
              onClick={() => {
                setShowGuestSignupModal(false);
                setCurrentIndex(prev => prev + 1);
                void logGuestEvent({ event_type: 'signup_prompt_dismissed', listing_id: pendingGuestLike?.listing_id ?? null });
                setPendingGuestLike(null);
              }}
            >
              Continue browsing as guest
            </Button>
          </Stack>
          <Text size="xs" c="dimmed">
            Already have an account?{' '}
            <span
              style={{ color: '#0ca678', cursor: 'pointer', fontWeight: 600 }}
              onClick={() => router.push('/login')}
            >
              Sign in
            </span>
          </Text>
        </Stack>
      </Modal>

    </Box>
  );
}
