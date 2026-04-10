'use client';

import { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../../app/contexts/AuthContext';
import { usePageTracking } from '../../../app/hooks/usePageTracking';
import { getLikedListings } from '../../../app/discover/likedListings';
import {
  createAppError,
  hasCompleteCorePreferences,
  normalizeRecommendationsError,
  parseApiErrorResponse,
} from '../../../../lib/errorHandling';
import {
  createRecommendationClientSessionId,
  createRecommendationEventId,
} from '../../../../lib/recommendationFeedback';
import { apiFetch } from '../../../../lib/api';
import {
  FEED_CACHE_TTL_MS,
  MATCHES_SCROLL_TRIGGER_PX,
  MATCHES_TOP_RETURN_PX,
  RETRY_COOLDOWN_SECONDS,
} from '../lib/constants';

export function useMatchesPage() {
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
      const res = await apiFetch(`/preferences/${userId}`, {}, { token });
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
  // Countdown seconds remaining before the user can manually retry after an error.
  const [retrySecondsLeft, setRetrySecondsLeft] = useState(0);
  // True when preferences or discover likes have changed since the last fetch.
  const [hasStaleChanges, setHasStaleChanges] = useState(false);
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
      const response = await apiFetch(
        `/interactions/recommendation-sessions/${feedbackSessionId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          keepalive,
        },
        { token: authState.accessToken }
      );

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
      const response = await apiFetch(
        `/interactions/recommendation-events`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
        },
        { token: authState.accessToken }
      );

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

    // Serve from localStorage when the cached result is still fresh.
    // Key is scoped to the user + their current preference location so any
    // location change automatically bypasses the cache.
    const lsCacheKey = `padly_rec_${userId}_${preferenceLocationKey}`;
    if (typeof window !== 'undefined' && preferenceLocationKey !== '||') {
      try {
        const raw = localStorage.getItem(lsCacheKey);
        if (raw) {
          const cached = JSON.parse(raw);
          if (cached?.ts && Date.now() - cached.ts < FEED_CACHE_TTL_MS && cached.result) {
            return cached.result;
          }
        }
      } catch {
        // localStorage unavailable or corrupt — continue with network fetch.
      }
    }

    let prefs = {};
    let hasCorePreferences = false;
    let behaviorSampleSize;
    const liked = getLikedListings();
    const likedExtras = {};

    const prefRes = await apiFetch(`/preferences/${userId}`, {}, { token });
    if (prefRes.ok) {
      const prefData = await prefRes.json();
      prefs = prefData.data || prefData || {};
      hasCorePreferences = hasCompleteCorePreferences(prefs);
    }

    if (!hasCorePreferences) {
      return { listings: [], missingCorePreferences: true, targetState: prefs.target_state_province ?? null };
    }

    try {
      const behaviorRes = await apiFetch(`/interactions/behavior/me?days=180`, {}, { token });
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

    const res = await apiFetch(
      `/recommendations`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
      { token }
    );

    if (!res.ok) {
      const apiError = await parseApiErrorResponse(res, 'Failed to fetch recommendations');
      throw createAppError(apiError.message, {
        status: apiError.status,
        payload: apiError.payload,
        rawMessage: apiError.message,
      });
    }

    const data = await res.json();
    const result = {
      listings: data.recommendations || [],
      missingCorePreferences: false,
      targetState: prefs.target_state_province ?? null,
      rankingContext: deriveRankingContext(data),
    };

    // Persist to localStorage so hard reloads within the TTL skip the API.
    if (typeof window !== 'undefined' && preferenceLocationKey !== '||') {
      try {
        localStorage.setItem(
          `padly_rec_${userId}_${preferenceLocationKey}`,
          JSON.stringify({ ts: Date.now(), result }),
        );
      } catch {
        // Storage full or unavailable — safe to ignore.
      }
    }

    return result;
  }, [deriveRankingContext, getValidToken, preferenceLocationKey, userId]);

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

  // Reset session state synchronously when the preference location changes so
  // the feedData sync below (also useLayoutEffect) can re-apply cache in the
  // same commit phase — preventing the old useEffect from wiping listings
  // after the layout effect had already restored them from the RQ cache.
  useLayoutEffect(() => {
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

  // Decrement retry countdown once per second until it reaches zero.
  useEffect(() => {
    if (retrySecondsLeft <= 0) return;
    const id = setTimeout(() => setRetrySecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearTimeout(id);
  }, [retrySecondsLeft]);

  const handleRetry = useCallback(() => {
    setRetrySecondsLeft(RETRY_COOLDOWN_SECONDS);
    refetchFeed();
  }, [refetchFeed]);

  // Returns true when preferences or discover likes have changed since the
  // last successful recommendations fetch for the current user + location.
  const checkStaleChanges = useCallback(() => {
    if (typeof window === 'undefined' || !userId || preferenceLocationKey === '||') return false;
    try {
      const staleAt = Number(localStorage.getItem(`padly_matches_stale_at_${userId}`) ?? 0);
      if (!staleAt) return false;
      const cacheRaw = localStorage.getItem(`padly_rec_${userId}_${preferenceLocationKey}`);
      const lastFetchTs = cacheRaw ? (JSON.parse(cacheRaw)?.ts ?? 0) : 0;
      return staleAt > lastFetchTs;
    } catch {
      return false;
    }
  }, [userId, preferenceLocationKey]);

  // Check for stale changes on mount and whenever the user returns to the tab.
  useEffect(() => {
    setHasStaleChanges(checkStaleChanges());
  }, [checkStaleChanges]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        setHasStaleChanges(checkStaleChanges());
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [checkStaleChanges]);

  const handleReloadMatches = useCallback(() => {
    // Clear the stale signal and the localStorage cache so fetchMatchesFeed
    // hits the API instead of returning the cached result.
    if (typeof window !== 'undefined' && userId) {
      try {
        localStorage.removeItem(`padly_matches_stale_at_${userId}`);
        localStorage.removeItem(`padly_rec_${userId}_${preferenceLocationKey}`);
      } catch {
        // Ignore storage errors.
      }
    }
    setHasStaleChanges(false);
    refetchFeed();
  }, [preferenceLocationKey, refetchFeed, userId]);

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
        const response = await apiFetch(
          `/interactions/recommendation-sessions`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildSessionPayload(listings, rankingContext)),
          },
          { token: authState.accessToken }
        );

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
        apiFetch(
          `/interactions/recommendation-sessions/${sessionId}`,
          {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
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
          },
          { token }
        ).catch(() => {});
      }).catch(() => {});
    };
  }, []);

  const submitFeedback = useCallback(async ({ feedbackLabel, reasonLabel = null }) => {
    if (!authState?.accessToken || !feedbackSessionId || feedbackSubmitting) return;

    setFeedbackSubmitting(true);
    try {
      const response = await apiFetch(
        `/interactions/recommendation-feedback`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            recommendation_session_id: feedbackSessionId,
            feedback_label: feedbackLabel,
            reason_label: reasonLabel,
          }),
        },
        { token: authState.accessToken }
      );

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

  return {
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
  };
}
