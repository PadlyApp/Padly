'use client';

import { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useHotkeys } from '@mantine/hooks';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../../app/contexts/AuthContext';
import { usePadlyTour } from '../../../app/contexts/TourContext';
import { usePageTracking } from '../../../app/hooks/usePageTracking';
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
import { getLikedListings, saveLikedListing } from '../../../app/discover/likedListings';
import {
  DISCOVER_FEEDBACK_SWIPE_THRESHOLD,
  DISCOVER_ALGORITHM_VERSION,
  clearDiscoverProgress,
  loadDiscoverProgress,
  saveDiscoverProgress,
  getOrCreateSwipeSessionId,
  collectDeviceContext,
} from '../lib/session';

export function useDiscoverPage() {
  const { user, getValidToken, authState, isAuthenticated, isLoading: authLoading } = useAuth();
  const { tourPhase } = usePadlyTour();
  const userId = user?.profile?.id;
  const router = useRouter();

  // Lightweight prefs fetch — only used to key the feed query on city so
  // changing location always triggers a fresh fetch.
  const { data: prefsData } = useQuery({
    queryKey: ['user-prefs', userId],
    queryFn: async () => {
      const token = await getValidToken();
      if (!token) return null;
      const res = await apiFetch(`/preferences/${userId}`, {}, { token });
      if (!res.ok) return null;
      const d = await res.json();
      return d.data || d || null;
    },
    enabled: !!userId,
    staleTime: 0,
  });
  const prefCity = prefsData?.target_city ?? null;
  usePageTracking('discover', authState?.accessToken);

  // ── guest mode ─────────────────────────────────────────────────────────────
  const isGuest = !authLoading && !isAuthenticated;

  // Guest preferences from sessionStorage — read once on mount, never changes
  const [guestPrefs] = useState(() => {
    if (typeof window === 'undefined') return {};
    try { return JSON.parse(sessionStorage.getItem('guest_preferences') || '{}'); } catch { return {}; }
  });
  const guestCity = guestPrefs?.target_city ?? null;

  // Stable guest session ID — follows the same ref-init pattern used for
  // recommendationClientSessionIdRef elsewhere in this file
  const guestSessionIdRef = useRef(null);
  if (!guestSessionIdRef.current && typeof window !== 'undefined') {
    try {
      const _existing = sessionStorage.getItem('padly_guest_session_id');
      if (_existing) {
        guestSessionIdRef.current = _existing;
      } else {
        const _newId = crypto.randomUUID?.() ?? `guest-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        sessionStorage.setItem('padly_guest_session_id', _newId);
        guestSessionIdRef.current = _newId;
      }
    } catch { /* best-effort */ }
  }

  const guestSwipeCountRef = useRef(0);
  const guestNudgeShownRef = useRef(false);
  const guestLikeCountRef = useRef(0); // tracks total guest likes to throttle the signup modal
  const [guestNudgeShown, setGuestNudgeShown] = useState(false);
  const [showGuestSignupModal, setShowGuestSignupModal] = useState(false);
  const [pendingGuestLike, setPendingGuestLike] = useState(null);

  /** Bumps React Query cache key so a refetch always reapplies stack state (refetch alone can reuse the same data reference). */
  const [feedReloadNonce, setFeedReloadNonce] = useState(0);

  const [listings, setListings] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [appendLoading, setAppendLoading] = useState(false);
  const [appendError, setAppendError] = useState(null);
  const [missingCorePreferences, setMissingCorePreferences] = useState(false);
  const [emptyResultReason, setEmptyResultReason] = useState(null);
  const [expandedListing, setExpandedListing] = useState(null);
  const [expandedImageIndex, setExpandedImageIndex] = useState(0);
  const [fullscreenOpen, setFullscreenOpen] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const swipeSessionIdRef = useRef(null);
  const recommendationClientSessionIdRef = useRef(null);
  const nextOffsetRef = useRef(0);
  // Tracks the last feedData object seen so we only sync on a genuine new result
  const prevFeedDataRef = useRef(null);
  const restoredProgressRef = useRef(false);
  // Stable refs for currentIndex and listings so handleSwipe doesn't need them as deps
  const currentIndexRef = useRef(currentIndex);
  const listingsRef = useRef(listings);
  useEffect(() => { currentIndexRef.current = currentIndex; }, [currentIndex]);
  useEffect(() => { listingsRef.current = listings; }, [listings]);

  const activeFilterBodyRef = useRef({});
  const cardViewStartRef = useRef(null);
  const cardPhotoCountRef = useRef(0);
  const cardExpandedRef = useRef(false);
  const expandedOpenedAtRef = useRef(null);
  const surfaceStartedAtRef = useRef(Date.now());
  const promptShownRef = useRef(false);
  const latestSessionIdRef = useRef(null);
  const latestTokenRef = useRef(null);
  const latestListingsRef = useRef([]);
  const latestRankingContextRef = useRef(null);
  const sessionMetricsRef = useRef({ likesCount: 0, detailOpensCount: 0, swipesCount: 0 });

  const [rankingContext, setRankingContext] = useState(null);
  const [feedbackSessionId, setFeedbackSessionId] = useState(null);
  const [promptAllowed, setPromptAllowed] = useState(false);
  const [showFeedbackPrompt, setShowFeedbackPrompt] = useState(false);
  const [feedbackStep, setFeedbackStep] = useState('question');
  const [pendingFeedbackLabel, setPendingFeedbackLabel] = useState(null);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackAcknowledged, setFeedbackAcknowledged] = useState(false);
  const [feedbackCycle, setFeedbackCycle] = useState(0);
  const [swipesInCycle, setSwipesInCycle] = useState(0);

  if (!recommendationClientSessionIdRef.current && typeof window !== 'undefined') {
    recommendationClientSessionIdRef.current = createRecommendationClientSessionId('discover');
  }

  const deriveRankingContext = useCallback((payload) => {
    const responseContext = payload?.ranking_context;
    if (responseContext) return responseContext;

    const recommendations = payload?.recommendations || [];
    const hasMlScores = recommendations.some((listing) => listing?.ml_score != null);
    return {
      algorithm_version: recommendations[0]?.algorithm_version ?? DISCOVER_ALGORITHM_VERSION,
      model_version: hasMlScores ? 'recommender-v1' : null,
      experiment_name: recommendations.length > 0 ? 'discover_ranker_v1' : null,
      experiment_variant: recommendations.length > 0 ? (hasMlScores ? 'two_tower' : 'baseline') : null,
    };
  }, []);

  const buildSessionPayload = useCallback((recommendations = listings, context = rankingContext) => {
    if (!recommendationClientSessionIdRef.current) {
      recommendationClientSessionIdRef.current = createRecommendationClientSessionId('discover');
    }

    const topListingIds = recommendations
      .map((listing) => listing?.listing_id)
      .filter(Boolean)
      .slice(0, 20);
    const hasMlScores = recommendations.some((listing) => listing?.ml_score != null);

    return {
      client_session_id: recommendationClientSessionIdRef.current,
      surface: 'discover',
      recommendation_count_shown: recommendations.length,
      top_listing_ids_shown: topListingIds,
      algorithm_version: context?.algorithm_version ?? recommendations[0]?.algorithm_version ?? DISCOVER_ALGORITHM_VERSION,
      model_version: context?.model_version ?? (hasMlScores ? 'recommender-v1' : null),
      experiment_name: context?.experiment_name ?? (recommendations.length > 0 ? 'discover_ranker_v1' : null),
      experiment_variant: context?.experiment_variant ?? (recommendations.length > 0 ? (hasMlScores ? 'two_tower' : 'baseline') : null),
    };
  }, [listings, rankingContext]);

  const startNextFeedbackCycle = useCallback(() => {
    recommendationClientSessionIdRef.current = createRecommendationClientSessionId('discover');
    sessionMetricsRef.current = { likesCount: 0, detailOpensCount: 0, swipesCount: 0 };
    setSwipesInCycle(0);
    setFeedbackSessionId(null);
    setPromptAllowed(false);
    setShowFeedbackPrompt(false);
    setFeedbackStep('question');
    setPendingFeedbackLabel(null);
    promptShownRef.current = false;
    surfaceStartedAtRef.current = Date.now();
    setFeedbackCycle((current) => current + 1);
  }, []);

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
        console.warn('Failed to update discover recommendation session');
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
            surface: 'discover',
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
        console.warn('Failed to persist discover recommendation event');
      }
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken, feedbackSessionId]);

  // ── shared fetch helper (used by the query AND loadMore) ──────────────────

  const fetchFeedPage = useCallback(async ({ offset = 0 } = {}) => {
    // Guest path — no auth token, preferences come from sessionStorage
    if (!userId) {
      let localGuestPrefs = {};
      try { localGuestPrefs = JSON.parse(sessionStorage.getItem('guest_preferences') || '{}'); } catch {}
      if (!localGuestPrefs.target_city) {
        return { listings: [], prefs: localGuestPrefs, hasCorePreferences: false, hasMore: false, nextOffset: 0 };
      }
      const body = {
        target_city: localGuestPrefs.target_city,
        target_country: localGuestPrefs.target_country || undefined,
        target_state_province: localGuestPrefs.target_state_province || undefined,
        budget_min: localGuestPrefs.budget_min || undefined,
        budget_max: localGuestPrefs.budget_max || undefined,
        required_bedrooms: localGuestPrefs.required_bedrooms || undefined,
        target_bathrooms: localGuestPrefs.target_bathrooms || undefined,
        top_n: 20,
        offset: 0,
      };
      activeFilterBodyRef.current = body;
      const res = await apiFetch(`/recommendations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to fetch recommendations');
      const data = await res.json();
      return {
        listings: data.recommendations || [],
        prefs: localGuestPrefs,
        hasCorePreferences: true,
        hasMore: false,
        nextOffset: 0,
        rankingContext: deriveRankingContext(data),
      };
    }

    const token = await getValidToken();
    if (!token) throw new Error('Not authenticated');

    let prefs = {};
    let hasCorePreferences = false;
    const swipedIds = new Set();

    const prefRes = await apiFetch(`/preferences/${userId}`, {}, { token });
    if (prefRes.ok) {
      const prefData = await prefRes.json();
      prefs = prefData.data || prefData || {};
      hasCorePreferences = hasCompleteCorePreferences(prefs);
    }

    if (!hasCorePreferences) {
      return { listings: [], prefs, hasCorePreferences, hasMore: false, nextOffset: 0 };
    }

    try {
      const swipesRes = await apiFetch(`/interactions/swipes/me?limit=500`, {}, { token });
      if (swipesRes.ok) {
        const swipesPayload = await swipesRes.json();
        for (const event of swipesPayload?.data || []) {
          if (event?.listing_id) swipedIds.add(event.listing_id);
        }
      }
    } catch {
      // Swipe history fetch is optional; fall back to local liked cache only.
    }

    const liked = getLikedListings();
    const likedExtras = {};
    let behaviorSampleSize;

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
      budget_min:      prefs.budget_min     ?? undefined,
      budget_max:      prefs.budget_max     ?? undefined,
      target_country: prefs.target_country ?? undefined,
      target_state_province: prefs.target_state_province ?? undefined,
      target_city: prefs.target_city ?? undefined,
      required_bedrooms: prefs.required_bedrooms ?? undefined,
      target_bathrooms: prefs.target_bathrooms ?? undefined,
      desired_beds:    prefs.required_bedrooms ?? undefined,
      desired_baths:   prefs.target_bathrooms  ?? undefined,
      target_deposit_amount: prefs.target_deposit_amount ?? undefined,
      furnished_preference: prefs.furnished_preference ?? undefined,
      gender_policy: prefs.gender_policy ?? undefined,
      target_lease_type: prefs.target_lease_type ?? undefined,
      target_lease_duration_months: prefs.target_lease_duration_months ?? undefined,
      allow_larger_layouts: prefs?.lifestyle_preferences?.allow_larger_layouts ?? undefined,
      move_in_date: prefs.move_in_date ?? undefined,
      target_furnished: prefs.target_furnished ?? undefined,
      wants_furnished:
        prefs.furnished_preference === 'required' || prefs.furnished_preference === 'preferred'
          ? 1
          : prefs.target_furnished === true
            ? 1
            : undefined,
      pref_lat:        prefs.target_latitude   ?? undefined,
      pref_lon:        prefs.target_longitude  ?? undefined,
      top_n: 50,
      offset,
      behavior_sample_size: behaviorSampleSize,
      ...likedExtras,
    };

    // Cache the filter body so swipe-context events can reference it.
    activeFilterBodyRef.current = body;

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
    const nextRankingContext = deriveRankingContext(data);

    const likedIds = new Set(getLikedListings().map((l) => l.listing_id));
    const fresh = (data.recommendations || []).filter(
      (l) => !likedIds.has(l.listing_id) && !swipedIds.has(l.listing_id)
    );

    // Fire search query event — best-effort.
    void apiFetch(
      `/interactions/search-queries`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: getOrCreateSwipeSessionId(),
          filter_snapshot: body,
          results_returned: (data.recommendations || []).length,
          offset,
        }),
      },
      { token }
    ).catch(() => {});

    return {
      listings: fresh,
      prefs,
      hasCorePreferences,
      hasMore: Boolean(data.has_more),
      nextOffset: (data.offset || 0) + (data.count || 0),
      rankingContext: nextRankingContext,
    };
  }, [deriveRankingContext, getValidToken, userId]);

  // ── cached initial feed (5-min stale time) ─────────────────────────────────

  const {
    data: feedData,
    isLoading: feedLoading,
    error: feedQueryError,
  } = useQuery({
    queryKey: isGuest
      ? ['discover-feed-guest', guestCity, feedReloadNonce]
      : ['discover-feed', userId, prefCity, feedReloadNonce],
    queryFn: () => fetchFeedPage({ offset: 0 }),
    enabled: isGuest ? !!guestCity : (!!userId && prefCity !== null),
    staleTime: 0,
    gcTime:    10 * 60 * 1000,
    retry: false,
  });

  const handleDiscoverFeedReload = useCallback(() => {
    if (!userId) return;
    clearDiscoverProgress(userId);
    prevFeedDataRef.current = null;
    setFeedReloadNonce((n) => n + 1);
  }, [userId]);

  useLayoutEffect(() => {
    if (!userId) return;

    const restored = loadDiscoverProgress(userId);
    if (!restored) return;

    // If the user changed their city since this progress was saved, discard it.
    if (prefCity && restored.targetCity && restored.targetCity !== prefCity) {
      clearDiscoverProgress(userId);
      return;
    }

    restoredProgressRef.current = true;
    setListings(Array.isArray(restored.listings) ? restored.listings : []);
    setCurrentIndex(
      Number.isFinite(restored.currentIndex)
        ? Math.max(0, Math.min(restored.currentIndex, restored.listings?.length || 0))
        : 0
    );
    setHasMore(Boolean(restored.hasMore));
    setMissingCorePreferences(Boolean(restored.missingCorePreferences));
    setEmptyResultReason(restored.emptyResultReason ?? null);
    setRankingContext(restored.rankingContext ?? null);
    nextOffsetRef.current = Number.isFinite(restored.nextOffset) ? restored.nextOffset : 0;
  }, [userId]);

  // Sync query data → swipe-stack state.
  // useLayoutEffect runs before paint so there is no visible flash of empty state on
  // remounts that have a cache hit (feedData is available immediately).
  useLayoutEffect(() => {
    if (!feedData || feedData === prevFeedDataRef.current) return;
    prevFeedDataRef.current = feedData;
    if (restoredProgressRef.current) {
      restoredProgressRef.current = false;
      return;
    }
    setListings(feedData.listings);
    setCurrentIndex(0);
    setHasMore(feedData.hasMore);
    setMissingCorePreferences(!feedData.hasCorePreferences);
    setRankingContext(feedData.rankingContext ?? null);
    setEmptyResultReason(
      feedData.listings.length === 0
        ? (feedData.hasCorePreferences ? 'strict_constraints' : 'missing_preferences')
        : null
    );
    nextOffsetRef.current = feedData.nextOffset;
    sessionMetricsRef.current = { likesCount: 0, detailOpensCount: 0, swipesCount: 0 };
    setSwipesInCycle(0);
    setFeedbackCycle(0);
    promptShownRef.current = false;
    setFeedbackSessionId(null);
    setPromptAllowed(false);
    setShowFeedbackPrompt(false);
    setFeedbackStep('question');
    setPendingFeedbackLabel(null);
    setFeedbackAcknowledged(false);
    surfaceStartedAtRef.current = Date.now();
    recommendationClientSessionIdRef.current = createRecommendationClientSessionId('discover');
  }, [feedData]);

  // Only show the full-page spinner on the very first load (no cached data yet).
  const loading = (feedLoading && !feedData) || appendLoading;
  const error = feedQueryError ? normalizeRecommendationsError(feedQueryError) : appendError;

  // ── append more listings ───────────────────────────────────────────────────

  const loadMore = useCallback(async () => {
    setAppendLoading(true);
    setAppendError(null);
    try {
      const page = await fetchFeedPage({ offset: nextOffsetRef.current });
      setHasMore(page.hasMore);
      nextOffsetRef.current = page.nextOffset;
      setListings((prev) => [...prev, ...page.listings]);
    } catch (err) {
      setAppendError(normalizeRecommendationsError(err));
    } finally {
      setAppendLoading(false);
    }
  }, [fetchFeedPage]);

  useEffect(() => {
    latestSessionIdRef.current = feedbackSessionId;
  }, [feedbackSessionId]);

  useEffect(() => {
    latestTokenRef.current = getValidToken;
  }, [getValidToken]);

  useEffect(() => {
    latestListingsRef.current = listings;
  }, [listings]);

  useEffect(() => {
    latestRankingContextRef.current = rankingContext;
  }, [rankingContext]);

  useEffect(() => {
    if (!userId) return;

    if (listings.length === 0 && currentIndex === 0) {
      clearDiscoverProgress(userId);
      return;
    }

    saveDiscoverProgress(userId, {
      listings,
      currentIndex,
      hasMore,
      nextOffset: nextOffsetRef.current,
      missingCorePreferences,
      emptyResultReason,
      rankingContext,
      targetCity: prefCity,
    });
  }, [
    currentIndex,
    emptyResultReason,
    hasMore,
    listings,
    missingCorePreferences,
    rankingContext,
    userId,
  ]);

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
          console.warn('Failed to create discover recommendation session');
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
  }, [authState?.accessToken, buildSessionPayload, error, feedbackCycle, listings, loading, rankingContext, userId]);

  useEffect(() => {
    if (
      promptShownRef.current ||
      !feedbackSessionId ||
      !promptAllowed ||
      showFeedbackPrompt ||
      feedbackSubmitting ||
      loading ||
      error ||
      swipesInCycle < DISCOVER_FEEDBACK_SWIPE_THRESHOLD
    ) {
      return;
    }

    promptShownRef.current = true;
    setShowFeedbackPrompt(true);
    void patchRecommendationSession({
      prompt_presented: true,
      likes_count: sessionMetricsRef.current.likesCount,
      detail_opens_count: sessionMetricsRef.current.detailOpensCount,
      recommendation_count_shown: listings.length,
      top_listing_ids_shown: listings.map((listing) => listing?.listing_id).filter(Boolean).slice(0, 20),
      surface_dwell_ms: Math.max(0, Date.now() - surfaceStartedAtRef.current),
      algorithm_version: rankingContext?.algorithm_version ?? DISCOVER_ALGORITHM_VERSION,
      model_version: rankingContext?.model_version ?? null,
      experiment_name: rankingContext?.experiment_name ?? 'discover_ranker_v1',
      experiment_variant: rankingContext?.experiment_variant ?? null,
    });
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
    swipesInCycle,
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
              likes_count: metrics.likesCount,
              detail_opens_count: metrics.detailOpensCount,
              recommendation_count_shown: recommendations.length,
              top_listing_ids_shown: topListingIds,
              algorithm_version: context?.algorithm_version ?? DISCOVER_ALGORITHM_VERSION,
              model_version: context?.model_version ?? (recommendations.some((listing) => listing?.ml_score != null) ? 'recommender-v1' : null),
              experiment_name: context?.experiment_name ?? (recommendations.length > 0 ? 'discover_ranker_v1' : null),
              experiment_variant: context?.experiment_variant ?? (recommendations.length > 0 ? (recommendations.some((listing) => listing?.ml_score != null) ? 'two_tower' : 'baseline') : null),
            }),
            keepalive: true,
          },
          { token }
        ).catch(() => {});
      }).catch(() => {});
    };
  }, []);

  useEffect(() => {
    setExpandedImageIndex(0);
  }, [expandedListing?.listing_id]);

  useEffect(() => {
    const remaining = listings.length - currentIndex;
    if (!loading && !error && hasMore && remaining === 0) {
      loadMore();
    }
  }, [currentIndex, listings.length, loading, error, hasMore, loadMore]);

  // ── swipe actions ─────────────────────────────────────────────────────────

  const persistSwipeEvent = useCallback(async ({ listing, action, position, startedAt }) => {
    if (!userId || !listing?.listing_id) return;
    const token = await getValidToken();
    if (!token) return;

    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }

    const algorithmVersion =
      listing?.algorithm_version != null && String(listing.algorithm_version).trim()
        ? String(listing.algorithm_version).trim()
        : DISCOVER_ALGORITHM_VERSION;

    try {
      const response = await apiFetch(
        `/interactions/swipes`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            listing_id: listing.listing_id,
            action,
            surface: 'discover',
            session_id: swipeSessionIdRef.current,
            position_in_feed: position,
            algorithm_version: algorithmVersion,
            model_version: listing?.ml_score != null ? 'recommender-v1' : null,
            city_filter: listing.city ?? null,
            latency_ms:
              startedAt != null && typeof performance !== 'undefined'
                ? Math.max(0, Math.round(performance.now() - startedAt))
                : undefined,
          }),
        },
        { token }
      );

      if (!response.ok && response.status !== 503) {
        console.warn('Failed to persist swipe interaction');
      }
    } catch {
      // Best-effort only.
    }
  }, [userId, getValidToken]);

  const persistSwipeContextEvent = useCallback(async ({ listing, action }) => {
    if (!authState?.accessToken || !listing?.listing_id) return;
    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }
    try {
      await apiFetch(
        `/interactions/swipe-context`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            listing_id: listing.listing_id,
            action,
            session_id: swipeSessionIdRef.current,
            active_filters_snapshot: activeFilterBodyRef.current || null,
            device_context: collectDeviceContext(),
          }),
        },
        { token: authState.accessToken }
      );
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken]);

  const persistListingViewEvent = useCallback(async ({ listing, surface }) => {
    if (!authState?.accessToken || !listing?.listing_id) return;
    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }
    const duration_ms =
      cardViewStartRef.current != null
        ? Math.max(0, Date.now() - cardViewStartRef.current)
        : null;
    try {
      await apiFetch(
        `/interactions/listing-views`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            listing_id: listing.listing_id,
            surface,
            session_id: swipeSessionIdRef.current,
            view_duration_ms: duration_ms,
            expanded: cardExpandedRef.current,
            photos_viewed_count: cardPhotoCountRef.current,
          }),
        },
        { token: authState.accessToken }
      );
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken]);

  // Reset view-tracking refs whenever the top card changes.
  useEffect(() => {
    if (listings.length === 0 || currentIndex >= listings.length) return;
    cardViewStartRef.current = Date.now();
    cardPhotoCountRef.current = 0;
    cardExpandedRef.current = false;
  }, [currentIndex, listings.length]);

  // ── guest event logger ────────────────────────────────────────────────────
  const logGuestEvent = useCallback(async (eventData) => {
    if (!isGuest) return;
    try {
      let localPrefs = {};
      try { localPrefs = JSON.parse(sessionStorage.getItem('guest_preferences') || '{}'); } catch {}
      void apiFetch(`/interactions/guest-events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guest_session_id: guestSessionIdRef.current ?? 'unknown',
          guest_prefs_snapshot: localPrefs,
          device_context: collectDeviceContext(),
          ...eventData,
        }),
      }).catch(() => {});
    } catch { /* best-effort */ }
  }, [isGuest]);

  // Stable handleSwipe: reads currentIndex/listings from refs so the callback
  // identity doesn't change on every swipe (prevents SwipeCard re-renders).

  const handleSwipe = useCallback((direction, listing) => {
    const action = direction === 'right' ? 'like' : 'pass';

    // ── Guest interception ────────────────────────────────────────────────────
    if (isGuest) {
      const position = listingsRef.current.findIndex(l => l.listing_id === listing?.listing_id);
      void logGuestEvent({
        event_type: action === 'like' ? 'swipe_right' : 'swipe_left',
        listing_id: listing?.listing_id ?? null,
        position_in_feed: position >= 0 ? position : currentIndexRef.current,
      });

      guestSwipeCountRef.current += 1;

      if (action === 'like') {
        guestLikeCountRef.current += 1;
        const likeCount = guestLikeCountRef.current;
        // Show the modal on the 1st like and every 10th after that (1, 10, 20, 30…)
        if (likeCount === 1 || likeCount % 10 === 0) {
          setPendingGuestLike(listing);
          setShowGuestSignupModal(true);
          void logGuestEvent({ event_type: 'signup_prompt_shown', listing_id: listing?.listing_id ?? null });
          return; // don't advance until modal is dismissed
        }
        // All other likes: just advance
        setCurrentIndex(prev => prev + 1);
        return;
      }

      // Pass — advance card
      setCurrentIndex(prev => prev + 1);

      // Show nudge after 5 swipes
      if (guestSwipeCountRef.current >= 15 && !guestNudgeShownRef.current) {
        guestNudgeShownRef.current = true;
        setGuestNudgeShown(true);
      }
      return;
    }
    // ─────────────────────────────────────────────────────────────────────────

    if (action === 'like') saveLikedListing(listing);

    const currentListings = listingsRef.current;
    const currentIdx = currentIndexRef.current;
    const top = currentListings[currentIdx];
    const position =
      top && listing?.listing_id === top.listing_id
        ? currentIdx
        : currentListings.findIndex((item) => item.listing_id === listing?.listing_id);
    const startedAt = typeof performance !== 'undefined' ? performance.now() : null;

    // Fire data logging events before advancing the index (best-effort, parallel).
    void persistListingViewEvent({ listing, surface: 'discover_card' });
    void persistSwipeContextEvent({ listing, action });

    void persistSwipeEvent({
      listing,
      action,
      position: position >= 0 ? position : currentIdx,
      startedAt,
    });

    sessionMetricsRef.current.swipesCount += 1;
    setSwipesInCycle(sessionMetricsRef.current.swipesCount);
    if (action === 'like') {
      sessionMetricsRef.current.likesCount += 1;
      // Signal to the Matches page that behaviour has changed so it can offer
      // a "Reload Matches" button the next time the user visits.
      if (userId && typeof window !== 'undefined') {
        try {
          localStorage.setItem(`padly_matches_stale_at_${userId}`, String(Date.now()));
        } catch {
          // Ignore storage errors.
        }
      }
    }

    setCurrentIndex((prev) => prev + 1);

    if (tourPhase === 'discover') {
      window.dispatchEvent(new CustomEvent('padly-tour-swipe', {
        detail: { direction },
      }));
    }
  }, [persistSwipeEvent, persistListingViewEvent, persistSwipeContextEvent, tourPhase, isGuest, logGuestEvent]);

  const handleButton = (direction) => {
    if (currentIndexRef.current >= listingsRef.current.length) return;
    handleSwipe(direction, listingsRef.current[currentIndexRef.current]);
  };

  const handleModalAction = (direction) => {
    closeExpanded();
    setTimeout(() => handleButton(direction), 200);
  };

  const openExpanded = useCallback((listing) => {
    cardExpandedRef.current = true;
    sessionMetricsRef.current.detailOpensCount += 1;
    const position = findListingPosition(listing?.listing_id);
    void persistRecommendationEvent({
      eventType: 'detail_open',
      listingId: listing?.listing_id,
      positionInFeed: position,
      metadata: {
        match_percent: listing?.match_percent ?? null,
        open_type: 'discover_quick_view',
      },
    });
    expandedOpenedAtRef.current = Date.now();
    setExpandedImageIndex(0);
    setExpandedListing(listing);
  }, [findListingPosition, persistRecommendationEvent]);

  const closeExpanded = useCallback(() => {
    if (expandedListing?.listing_id) {
      const position = findListingPosition(expandedListing.listing_id);
      const dwellMs =
        expandedOpenedAtRef.current != null
          ? Math.max(0, Date.now() - expandedOpenedAtRef.current)
          : null;
      void persistRecommendationEvent({
        eventType: 'detail_view',
        listingId: expandedListing.listing_id,
        positionInFeed: position,
        dwellMs,
        metadata: {
          view_type: 'discover_quick_view',
        },
      });
    }

    expandedOpenedAtRef.current = null;
    setExpandedListing(null);
  }, [expandedListing, findListingPosition, persistRecommendationEvent]);

  const submitFeedback = useCallback(async ({ feedbackLabel, reasonLabel = null }) => {
    if (!authState?.accessToken || !feedbackSessionId || feedbackSubmitting) return;

    setFeedbackSubmitting(true);
    try {
      await patchRecommendationSession({
        likes_count: sessionMetricsRef.current.likesCount,
        detail_opens_count: sessionMetricsRef.current.detailOpensCount,
        recommendation_count_shown: listings.length,
        top_listing_ids_shown: listings.map((listing) => listing?.listing_id).filter(Boolean).slice(0, 20),
        surface_dwell_ms: Math.max(0, Date.now() - surfaceStartedAtRef.current),
        algorithm_version: rankingContext?.algorithm_version ?? DISCOVER_ALGORITHM_VERSION,
        model_version: rankingContext?.model_version ?? null,
        experiment_name: rankingContext?.experiment_name ?? 'discover_ranker_v1',
        experiment_variant: rankingContext?.experiment_variant ?? null,
      });

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
        console.warn('Failed to submit discover recommendation feedback');
        return;
      }

      setShowFeedbackPrompt(false);
      setPromptAllowed(false);
      setFeedbackStep('question');
      setPendingFeedbackLabel(null);
      setFeedbackAcknowledged(true);
      startNextFeedbackCycle();
    } catch {
      // Best-effort only.
    } finally {
      setFeedbackSubmitting(false);
    }
  }, [
    authState?.accessToken,
    feedbackSessionId,
    feedbackSubmitting,
    listings,
    patchRecommendationSession,
    rankingContext,
    startNextFeedbackCycle,
  ]);

  const dismissFeedbackPrompt = useCallback(async () => {
    await patchRecommendationSession({
      prompt_dismissed: true,
      likes_count: sessionMetricsRef.current.likesCount,
      detail_opens_count: sessionMetricsRef.current.detailOpensCount,
      surface_dwell_ms: Math.max(0, Date.now() - surfaceStartedAtRef.current),
    });
    startNextFeedbackCycle();
  }, [patchRecommendationSession, startNextFeedbackCycle]);

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

  // Auto-advance modal images every 5s while modal is open
  useEffect(() => {
    if (!expandedListing) return;
    const imgs = (() => {
      const i = expandedListing.images;
      if (Array.isArray(i)) return i;
      if (typeof i === 'string') { try { return JSON.parse(i); } catch { return []; } }
      return [];
    })();
    if (imgs.length <= 1) return;
    const timer = setInterval(() => {
      setExpandedImageIndex(prev => (prev + 1) % imgs.length);
    }, 3000);
    return () => clearInterval(timer);
  }, [expandedListing]);

  const remaining = listings.length - currentIndex;
  const noRecommendations = !loading && !error && listings.length === 0 && !hasMore;
  const isDone = !loading && !error && listings.length > 0 && remaining === 0 && !hasMore;

  useHotkeys([
    ['ArrowLeft', () => handleButton('left')],
    ['ArrowRight', () => handleButton('right')],
  ]);

  return {
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
  };
}
