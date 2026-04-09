'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const MATCHES_SCROLL_TRIGGER_PX = 900;
const MATCHES_TOP_RETURN_PX = 120;

import { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Container, Title, Text, Grid, Card, Badge, Button, Stack, Box, ThemeIcon, Group } from '@mantine/core';
import { SkeletonListingCard } from '../components/Skeletons';
import { IconSparkles, IconMapPin } from '@tabler/icons-react';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { useAuth } from '../contexts/AuthContext';
import { usePageTracking } from '../hooks/usePageTracking';
import { getLikedListings } from '../discover/likedListings';
import { formatAmenityLabel, getActiveAmenityKeys } from '../../../lib/formatters';
import {
  createAppError,
  hasCompleteCorePreferences,
  normalizeRecommendationsError,
  parseApiErrorResponse,
} from '../../../lib/errorHandling';
import {
  MATCHES_FEEDBACK_CHOICES,
  MATCHES_NEGATIVE_REASON_CHOICES,
  createRecommendationClientSessionId,
  createRecommendationEventId,
} from '../../../lib/recommendationFeedback';

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
  const { user, getValidToken, authState } = useAuth();
  const userId = user?.profile?.id;

  // Keep feed cache keyed to current preference location so changing
  // preferences forces a fresh recommendations fetch.
  const { data: prefsData } = useQuery({
    queryKey: ['user-prefs', userId],
    queryFn: async () => {
      const token = await getValidToken();
      if (!token || !userId) return null;
      const res = await fetch(`${API_BASE}/api/preferences/${userId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      const data = await res.json();
      return data?.data || data || null;
    },
    enabled: !!userId,
    staleTime: 0,
  });

  const prefCountry = prefsData?.target_country ?? null;
  const prefState = prefsData?.target_state_province ?? null;
  const prefCity = prefsData?.target_city ?? null;
  const preferenceLocationKey = `${prefCountry || ''}|${prefState || ''}|${prefCity || ''}`;

  const clientSessionIdRef = useRef(null);
  const surfaceStartedAtRef = useRef(Date.now());
  const promptShownRef = useRef(false);
  const hasScrolledDeepRef = useRef(false);
  const sessionMetricsRef = useRef({ detailOpensCount: 0, savesCount: 0 });
  const latestSessionIdRef = useRef(null);
  const latestTokenRef = useRef(null);
  const latestListingsRef = useRef([]);
  const latestRankingContextRef = useRef(null);

  usePageTracking('matches', authState?.accessToken);

  const [listings, setListings] = useState([]);
  const [missingCorePreferences, setMissingCorePreferences] = useState(false);
  const [targetStateFallback, setTargetStateFallback] = useState(null);
  const [rankingContext, setRankingContext] = useState(null);
  const [feedbackSessionId, setFeedbackSessionId] = useState(null);
  const [promptAllowed, setPromptAllowed] = useState(false);
  const [showFeedbackPrompt, setShowFeedbackPrompt] = useState(false);
  const [feedbackStep, setFeedbackStep] = useState('question');
  const [pendingFeedbackLabel, setPendingFeedbackLabel] = useState(null);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackAcknowledged, setFeedbackAcknowledged] = useState(false);
  // Tracks the last feedData object seen so we only sync on a genuine new result
  const prevFeedDataRef = useRef(null);

  if (!clientSessionIdRef.current && typeof window !== 'undefined') {
    clientSessionIdRef.current = createRecommendationClientSessionId('matches');
  }

  const deriveRankingContext = useCallback((payload) => {
    const responseContext = payload?.ranking_context;
    if (responseContext) return responseContext;

    const recommendations = payload?.recommendations || [];
    const hasMlScores = recommendations.some((listing) => listing?.ml_score != null);
    return {
      algorithm_version: recommendations[0]?.algorithm_version ?? null,
      model_version: hasMlScores ? 'recommender-v1' : null,
      experiment_name: recommendations.length > 0 ? 'matches_ranker_v1' : null,
      experiment_variant: recommendations.length > 0 ? (hasMlScores ? 'two_tower' : 'baseline') : null,
    };
  }, []);

  const buildSessionPayload = useCallback((recommendations = listings, context = rankingContext) => {
    if (!clientSessionIdRef.current) {
      clientSessionIdRef.current = createRecommendationClientSessionId('matches');
    }

    const topListingIds = recommendations
      .map((listing) => listing?.listing_id)
      .filter(Boolean)
      .slice(0, 20);
    const hasMlScores = recommendations.some((listing) => listing?.ml_score != null);

    return {
      client_session_id: clientSessionIdRef.current,
      surface: 'matches',
      recommendation_count_shown: recommendations.length,
      top_listing_ids_shown: topListingIds,
      algorithm_version: context?.algorithm_version ?? recommendations[0]?.algorithm_version ?? null,
      model_version: context?.model_version ?? (hasMlScores ? 'recommender-v1' : null),
      experiment_name: context?.experiment_name ?? (recommendations.length > 0 ? 'matches_ranker_v1' : null),
      experiment_variant: context?.experiment_variant ?? (recommendations.length > 0 ? (hasMlScores ? 'two_tower' : 'baseline') : null),
    };
  }, [listings, rankingContext]);

  const patchRecommendationSession = useCallback(async (payload, { keepalive = false } = {}) => {
    if (!authState?.accessToken || !feedbackSessionId) return null;

    try {
      const response = await fetch(`${API_BASE}/api/interactions/recommendation-sessions/${feedbackSessionId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify(payload),
        keepalive,
      });

      if (!response.ok && response.status !== 503) {
        console.warn('Failed to update recommendation session');
        return null;
      }

      if (response.status === 503) return null;
      const result = await response.json();
      return result?.data ?? null;
    } catch {
      return null;
    }
  }, [authState?.accessToken, feedbackSessionId]);

  const findListingPosition = useCallback((listingId) => {
    if (!listingId) return null;
    const index = listings.findIndex((item) => item?.listing_id === listingId);
    return index >= 0 ? index : null;
  }, [listings]);

  const persistRecommendationEvent = useCallback(async ({
    eventType,
    listingId = null,
    positionInFeed = null,
    dwellMs = null,
    metadata = {},
    keepalive = false,
  }) => {
    if (!authState?.accessToken || !feedbackSessionId) return null;

    try {
      const response = await fetch(`${API_BASE}/api/interactions/recommendation-events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify({
          recommendation_session_id: feedbackSessionId,
          client_event_id: createRecommendationEventId(eventType),
          surface: 'matches',
          event_type: eventType,
          listing_id: listingId,
          position_in_feed: positionInFeed,
          dwell_ms: dwellMs,
          metadata,
        }),
        keepalive,
      });

      if (!response.ok && response.status !== 503) {
        console.warn('Failed to persist recommendation engagement event');
      }
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken, feedbackSessionId]);

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
      return { listings: [], missingCorePreferences: true, targetState: prefs.target_state_province ?? null };
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
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
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
    return {
      listings: data.recommendations || [],
      missingCorePreferences: false,
      targetState: prefs.target_state_province ?? null,
      rankingContext: deriveRankingContext(data),
    };
  }, [deriveRankingContext, getValidToken, userId]);

  const {
    data: feedData,
    isLoading: feedLoading,
    error: feedQueryError,
    refetch: refetchFeed,
  } = useQuery({
    queryKey: ['matches-feed', userId, preferenceLocationKey],
    queryFn: fetchMatchesFeed,
    enabled: !!userId,
    staleTime: 5 * 60 * 1000,
    gcTime:    10 * 60 * 1000,
    retry: false,
  });

  useEffect(() => {
    prevFeedDataRef.current = null;
    setListings([]);
    setMissingCorePreferences(false);
    setTargetStateFallback(null);
    setRankingContext(null);
    setFeedbackSessionId(null);
    setPromptAllowed(false);
    setShowFeedbackPrompt(false);
    setFeedbackStep('question');
    setPendingFeedbackLabel(null);
    setFeedbackAcknowledged(false);
    sessionMetricsRef.current = { detailOpensCount: 0, savesCount: 0 };
    surfaceStartedAtRef.current = Date.now();
    clientSessionIdRef.current = createRecommendationClientSessionId('matches');
    promptShownRef.current = false;
    hasScrolledDeepRef.current = false;
  }, [preferenceLocationKey]);

  // Sync query data → state without a visible flash on cache-hit remounts
  useLayoutEffect(() => {
    if (!feedData || feedData === prevFeedDataRef.current) return;
    prevFeedDataRef.current = feedData;
    setListings(feedData.listings);
    setMissingCorePreferences(feedData.missingCorePreferences);
    setTargetStateFallback(feedData.targetState ?? null);
    setRankingContext(feedData.rankingContext ?? null);
    setFeedbackSessionId(null);
    setPromptAllowed(false);
    setShowFeedbackPrompt(false);
    setFeedbackStep('question');
    setPendingFeedbackLabel(null);
    setFeedbackAcknowledged(false);
    sessionMetricsRef.current = { detailOpensCount: 0, savesCount: 0 };
    surfaceStartedAtRef.current = Date.now();
    clientSessionIdRef.current = createRecommendationClientSessionId('matches');
    promptShownRef.current = false;
    hasScrolledDeepRef.current = false;
  }, [feedData]);

  const loading = feedLoading && !feedData;
  const error = feedQueryError ? normalizeRecommendationsError(feedQueryError) : null;

  useEffect(() => {
    latestTokenRef.current = getValidToken;
  }, [getValidToken]);

  useEffect(() => {
    latestSessionIdRef.current = feedbackSessionId;
  }, [feedbackSessionId]);

  useEffect(() => {
    latestListingsRef.current = listings;
  }, [listings]);

  useEffect(() => {
    latestRankingContextRef.current = rankingContext;
  }, [rankingContext]);

  useEffect(() => {
    if (!authState?.accessToken || !userId || loading || error || listings.length === 0) return;

    let cancelled = false;

    const ensureRecommendationSession = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/interactions/recommendation-sessions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authState.accessToken}`,
          },
          body: JSON.stringify(buildSessionPayload(listings, rankingContext)),
        });

        if (!response.ok && response.status !== 503) {
          console.warn('Failed to create recommendation session');
          return;
        }

        if (response.status === 503) return;

        const result = await response.json();
        if (cancelled) return;

        setFeedbackSessionId(result?.data?.id ?? null);
        setPromptAllowed(Boolean(result?.prompt_allowed));
      } catch {
        // Best-effort only.
      }
    };

    void ensureRecommendationSession();

    return () => {
      cancelled = true;
    };
  }, [authState?.accessToken, buildSessionPayload, error, listings, loading, rankingContext, userId]);

  useEffect(() => {
    if (
      !feedbackSessionId ||
      !promptAllowed ||
      feedbackSubmitting ||
      loading ||
      error ||
      listings.length === 0
    ) {
      return undefined;
    }

    const handleScroll = () => {
      const scrollY = window.scrollY || window.pageYOffset || 0;

      if (scrollY >= MATCHES_SCROLL_TRIGGER_PX) {
        hasScrolledDeepRef.current = true;
      }

      if (
        hasScrolledDeepRef.current &&
        scrollY <= MATCHES_TOP_RETURN_PX &&
        !promptShownRef.current &&
        !showFeedbackPrompt
      ) {
        promptShownRef.current = true;
        setShowFeedbackPrompt(true);
        void patchRecommendationSession({
          prompt_presented: true,
          detail_opens_count: sessionMetricsRef.current.detailOpensCount,
          saves_count: sessionMetricsRef.current.savesCount,
          recommendation_count_shown: listings.length,
          top_listing_ids_shown: listings.map((listing) => listing?.listing_id).filter(Boolean).slice(0, 20),
          surface_dwell_ms: Math.max(0, Date.now() - surfaceStartedAtRef.current),
          algorithm_version: rankingContext?.algorithm_version ?? listings[0]?.algorithm_version ?? null,
          model_version: rankingContext?.model_version ?? (listings.some((listing) => listing?.ml_score != null) ? 'recommender-v1' : null),
          experiment_name: rankingContext?.experiment_name ?? (listings.length > 0 ? 'matches_ranker_v1' : null),
          experiment_variant: rankingContext?.experiment_variant ?? (listings.length > 0 ? (listings.some((listing) => listing?.ml_score != null) ? 'two_tower' : 'baseline') : null),
        });
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, [
    error,
    feedbackSessionId,
    feedbackSubmitting,
    listings,
    loading,
    patchRecommendationSession,
    promptAllowed,
    rankingContext,
    showFeedbackPrompt,
  ]);

  useEffect(() => {
    return () => {
      const getToken = latestTokenRef.current;
      const sessionId = latestSessionIdRef.current;
      if (!getToken || !sessionId) return;

      const recommendations = latestListingsRef.current || [];
      const context = latestRankingContextRef.current;
      const topListingIds = recommendations
        .map((listing) => listing?.listing_id)
        .filter(Boolean)
        .slice(0, 20);
      const dwellMs = Math.max(0, Date.now() - surfaceStartedAtRef.current);
      const metrics = { ...sessionMetricsRef.current };

      getToken().then((token) => {
        if (!token) return;
        fetch(`${API_BASE}/api/interactions/recommendation-sessions/${sessionId}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            mark_ended: true,
            surface_dwell_ms: dwellMs,
            detail_opens_count: metrics.detailOpensCount,
            saves_count: metrics.savesCount,
            recommendation_count_shown: recommendations.length,
            top_listing_ids_shown: topListingIds,
            algorithm_version: context?.algorithm_version ?? recommendations[0]?.algorithm_version ?? null,
            model_version: context?.model_version ?? (recommendations.some((listing) => listing?.ml_score != null) ? 'recommender-v1' : null),
            experiment_name: context?.experiment_name ?? (recommendations.length > 0 ? 'matches_ranker_v1' : null),
            experiment_variant: context?.experiment_variant ?? (recommendations.length > 0 ? (recommendations.some((listing) => listing?.ml_score != null) ? 'two_tower' : 'baseline') : null),
          }),
          keepalive: true,
        }).catch(() => {});
      }).catch(() => {});
    };
  }, []);

  const submitFeedback = useCallback(async ({ feedbackLabel, reasonLabel = null }) => {
    if (!authState?.accessToken || !feedbackSessionId || feedbackSubmitting) return;

    setFeedbackSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/api/interactions/recommendation-feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
        body: JSON.stringify({
          recommendation_session_id: feedbackSessionId,
          feedback_label: feedbackLabel,
          reason_label: reasonLabel,
        }),
      });

      if (!response.ok && response.status !== 503) {
        console.warn('Failed to submit recommendation feedback');
        return;
      }

      setShowFeedbackPrompt(false);
      setPromptAllowed(false);
      setFeedbackStep('question');
      setPendingFeedbackLabel(null);
      setFeedbackAcknowledged(true);
    } catch {
      // Best-effort only.
    } finally {
      setFeedbackSubmitting(false);
    }
  }, [authState?.accessToken, feedbackSessionId, feedbackSubmitting]);

  const dismissFeedbackPrompt = useCallback(async () => {
    await patchRecommendationSession({
      prompt_dismissed: true,
      detail_opens_count: sessionMetricsRef.current.detailOpensCount,
      saves_count: sessionMetricsRef.current.savesCount,
      surface_dwell_ms: Math.max(0, Date.now() - surfaceStartedAtRef.current),
    });
    setShowFeedbackPrompt(false);
    setPromptAllowed(false);
    setFeedbackStep('question');
    setPendingFeedbackLabel(null);
    setFeedbackAcknowledged(false);
  }, [patchRecommendationSession]);

  const handleFeedbackChoice = useCallback(async (value) => {
    if (value === 'not_useful') {
      setPendingFeedbackLabel(value);
      setFeedbackStep('reason');
      return;
    }

    await submitFeedback({ feedbackLabel: value });
  }, [submitFeedback]);

  const handleNegativeReason = useCallback(async (reasonLabel) => {
    await submitFeedback({
      feedbackLabel: pendingFeedbackLabel || 'not_useful',
      reasonLabel,
    });
  }, [pendingFeedbackLabel, submitFeedback]);

  const handleViewDetails = useCallback((listing) => {
    const position = findListingPosition(listing?.listing_id);
    sessionMetricsRef.current.detailOpensCount += 1;
    void persistRecommendationEvent({
      eventType: 'detail_open',
      listingId: listing?.listing_id,
      positionInFeed: position,
      metadata: {
        match_percent: listing?.match_percent ?? null,
      },
      keepalive: true,
    });

    const href = feedbackSessionId
      ? `/listings/${listing.listing_id}?source=matches&recommendationSessionId=${encodeURIComponent(feedbackSessionId)}${position != null ? `&position=${position}` : ''}`
      : `/listings/${listing.listing_id}?source=matches${position != null ? `&position=${position}` : ''}`;

    router.push(href);
  }, [feedbackSessionId, findListingPosition, persistRecommendationEvent, router]);

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
