'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const MATCHES_PROMPT_DELAY_MS = 10000;

import { useState, useEffect, useCallback, useRef } from 'react';
import { Container, Title, Text, Grid, Card, Badge, Button, Stack, Box, ThemeIcon, Tooltip } from '@mantine/core';
import { IconSparkles, IconStar, IconStarFilled } from '@tabler/icons-react';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { useAuth } from '../contexts/AuthContext';
import { usePageTracking } from '../hooks/usePageTracking';
import { getLikedListings } from '../discover/likedListings';
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

function MatchesPageContent() {
  const router = useRouter();
  const { user, authState } = useAuth();
  const userId = user?.profile?.id;
  const clientSessionIdRef = useRef(null);
  const surfaceStartedAtRef = useRef(Date.now());
  const promptTimerRef = useRef(null);
  const sessionMetricsRef = useRef({ detailOpensCount: 0, savesCount: 0 });
  const latestSessionIdRef = useRef(null);
  const latestTokenRef = useRef(null);
  const latestListingsRef = useRef([]);
  const latestRankingContextRef = useRef(null);

  usePageTracking('matches', authState?.accessToken);

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [missingCorePreferences, setMissingCorePreferences] = useState(false);
  const [userGroup, setUserGroup] = useState(null);
  const [savedListingIds, setSavedListingIds] = useState(new Set());
  const [rankingContext, setRankingContext] = useState(null);
  const [feedbackSessionId, setFeedbackSessionId] = useState(null);
  const [promptAllowed, setPromptAllowed] = useState(false);
  const [showFeedbackPrompt, setShowFeedbackPrompt] = useState(false);
  const [feedbackStep, setFeedbackStep] = useState('question');
  const [pendingFeedbackLabel, setPendingFeedbackLabel] = useState(null);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackAcknowledged, setFeedbackAcknowledged] = useState(false);

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
        return null;
      }

      return response.ok ? response.json() : null;
    } catch {
      return null;
    }
  }, [authState?.accessToken, feedbackSessionId]);

  const fetchMatches = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      let prefs = {};
      let hasCorePreferences = false;
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
          hasCorePreferences = hasCompleteCorePreferences(prefs);
        }
        setMissingCorePreferences(!hasCorePreferences);

        if (!hasCorePreferences) {
          setLoading(false);
          setListings([]);
          return;
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

      if (!res.ok) {
        const apiError = await parseApiErrorResponse(res, 'Failed to fetch ranked matches');
        throw createAppError(apiError.message, {
          status: apiError.status,
          payload: apiError.payload,
          rawMessage: apiError.message,
        });
      }

      const data = await res.json();
      setListings(data.recommendations || []);
      setRankingContext(deriveRankingContext(data));
    } catch (err) {
      setError(normalizeRecommendationsError(err));
    } finally {
      setLoading(false);
    }
  }, [userId, authState?.accessToken, deriveRankingContext]);

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

  useEffect(() => {
    latestTokenRef.current = authState?.accessToken ?? null;
  }, [authState?.accessToken]);

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
    window.clearTimeout(promptTimerRef.current);

    if (
      !feedbackSessionId ||
      !promptAllowed ||
      showFeedbackPrompt ||
      feedbackSubmitting ||
      loading ||
      error ||
      listings.length === 0
    ) {
      return undefined;
    }

    promptTimerRef.current = window.setTimeout(() => {
      setShowFeedbackPrompt(true);
      void patchRecommendationSession({ prompt_presented: true });
    }, MATCHES_PROMPT_DELAY_MS);

    return () => {
      window.clearTimeout(promptTimerRef.current);
    };
  }, [
    error,
    feedbackSessionId,
    feedbackSubmitting,
    listings.length,
    loading,
    patchRecommendationSession,
    promptAllowed,
    showFeedbackPrompt,
  ]);

  useEffect(() => {
    return () => {
      const token = latestTokenRef.current;
      const sessionId = latestSessionIdRef.current;

      if (!token || !sessionId) return;

      const recommendations = latestListingsRef.current || [];
      const context = latestRankingContextRef.current;
      const topListingIds = recommendations
        .map((listing) => listing?.listing_id)
        .filter(Boolean)
        .slice(0, 20);

      fetch(`${API_BASE}/api/interactions/recommendation-sessions/${sessionId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          mark_ended: true,
          surface_dwell_ms: Math.max(0, Date.now() - surfaceStartedAtRef.current),
          detail_opens_count: sessionMetricsRef.current.detailOpensCount,
          saves_count: sessionMetricsRef.current.savesCount,
          recommendation_count_shown: recommendations.length,
          top_listing_ids_shown: topListingIds,
          algorithm_version: context?.algorithm_version ?? recommendations[0]?.algorithm_version ?? null,
          model_version: context?.model_version ?? (recommendations.some((listing) => listing?.ml_score != null) ? 'recommender-v1' : null),
          experiment_name: context?.experiment_name ?? (recommendations.length > 0 ? 'matches_ranker_v1' : null),
          experiment_variant: context?.experiment_variant ?? (recommendations.length > 0 ? (recommendations.some((listing) => listing?.ml_score != null) ? 'two_tower' : 'baseline') : null),
        }),
        keepalive: true,
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
    setShowFeedbackPrompt(false);
    setPromptAllowed(false);
    setFeedbackStep('question');
    setPendingFeedbackLabel(null);
    await patchRecommendationSession({ prompt_dismissed: true });
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
    const nextDetailOpens = sessionMetricsRef.current.detailOpensCount + 1;
    sessionMetricsRef.current.detailOpensCount = nextDetailOpens;
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
      const position = findListingPosition(lid);
      void persistRecommendationEvent({
        eventType: isSaved ? 'unsave' : 'save',
        listingId: lid,
        positionInFeed: position,
        metadata: {
          group_id: userGroup.id,
        },
      });
      if (!isSaved) {
        const nextSaves = sessionMetricsRef.current.savesCount + 1;
        sessionMetricsRef.current.savesCount = nextSaves;
      }
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
          {feedbackAcknowledged && (
            <Text size="sm" c="teal.7">
              Thanks. Your feedback was saved for recommendation evaluation.
            </Text>
          )}
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
              <Title order={3} style={{ color: '#212529' }}>
                {missingCorePreferences ? 'Complete your preferences to get matches' : 'No ranked matches yet'}
              </Title>
              <Text size="md" c="dimmed" ta="center" maw={420}>
                {missingCorePreferences
                  ? 'Set your country, state/province, and city to start receiving location-aware listings.'
                  : 'Update your preferences or broaden a hard constraint to surface more listings.'}
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
                Go To Discover
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
                            onClick={() => handleViewDetails(listing)}
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
          </Stack>
        )}
      </Container>
    </Box>
  );
}
