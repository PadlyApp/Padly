'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DISCOVER_FEEDBACK_SWIPE_THRESHOLD = 10;

import { useState, useEffect, useCallback, useRef } from 'react';
import { Container, Box, Text, Title, Button, Stack, Loader, ActionIcon, Group, Progress, Modal, Badge, Divider, ThemeIcon } from '@mantine/core';
import { useHotkeys } from '@mantine/hooks';
import { IconX, IconHeart, IconRefresh, IconInfoCircle, IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { useRouter } from 'next/navigation';
import { Navigation } from '../components/Navigation';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { useAuth } from '../contexts/AuthContext';
import { usePadlyTour } from '../contexts/TourContext';
import { usePageTracking } from '../hooks/usePageTracking';
import { SwipeCard } from '../components/SwipeCard';
import {
  createAppError,
  hasCompleteCorePreferences,
  normalizeRecommendationsError,
  parseApiErrorResponse,
} from '../../../lib/errorHandling';
import {
  MATCHES_FEEDBACK_CHOICES,
  MATCHES_NEGATIVE_REASON_CHOICES,
  createRecommendationEventId,
} from '../../../lib/recommendationFeedback';

import { getLikedListings, saveLikedListing } from './likedListings';

// ── session helpers ─────────────────────────────────────────────────────────

const SWIPE_SESSION_KEY = 'padly_swipe_session_id';

/** Stable client label for swipe telemetry (backend requires algorithm_version). */
const DISCOVER_ALGORITHM_VERSION = 'discover-v1';

function getOrCreateSwipeSessionId() {
  if (typeof window === 'undefined') return 'server-session';
  const existing = sessionStorage.getItem(SWIPE_SESSION_KEY);
  if (existing) return existing;

  const generated = typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  sessionStorage.setItem(SWIPE_SESSION_KEY, generated);
  return generated;
}

function collectDeviceContext() {
  if (typeof window === 'undefined') return {};
  const ua = navigator.userAgent || '';
  const isTablet = /Tablet|iPad/i.test(ua);
  const isMobile = /Mobi|Android/i.test(ua);
  const deviceType = isTablet ? 'tablet' : isMobile ? 'mobile' : 'desktop';

  let os = 'unknown';
  if (/Windows/i.test(ua)) os = 'windows';
  else if (/Mac OS X/i.test(ua)) os = 'macos';
  else if (/Android/i.test(ua)) os = 'android';
  else if (/iPhone|iPad|iPod/i.test(ua)) os = 'ios';
  else if (/Linux/i.test(ua)) os = 'linux';

  let browser = 'unknown';
  if (/Firefox\/\d/i.test(ua)) browser = 'firefox';
  else if (/Edg\/\d/i.test(ua)) browser = 'edge';
  else if (/Chrome\/\d/i.test(ua) && !/Chromium/i.test(ua)) browser = 'chrome';
  else if (/Safari\/\d/i.test(ua) && !/Chrome/i.test(ua)) browser = 'safari';

  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  return {
    device_type: deviceType,
    os,
    browser,
    screen_width: window.screen?.width ?? null,
    screen_height: window.screen?.height ?? null,
    connection_type: conn?.effectiveType ?? conn?.type ?? null,
  };
}

// ── page ────────────────────────────────────────────────────────────────────

export default function DiscoverPage() {
  return (
    <ProtectedRoute>
      <DiscoverContent />
    </ProtectedRoute>
  );
}

function DiscoverContent() {
  const { user, authState } = useAuth();
  const { tourPhase } = usePadlyTour();
  const userId = user?.profile?.id;
  const router = useRouter();
  usePageTracking('discover', authState?.accessToken);

  const [listings, setListings] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [missingCorePreferences, setMissingCorePreferences] = useState(false);
  const [emptyResultReason, setEmptyResultReason] = useState(null);
  const [expandedListing, setExpandedListing] = useState(null);
  const [expandedImageIndex, setExpandedImageIndex] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const swipeSessionIdRef = useRef(null);
  const nextOffsetRef = useRef(0);
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

  if (!swipeSessionIdRef.current && typeof window !== 'undefined') {
    swipeSessionIdRef.current = createRecommendationEventId('discover-session');
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
    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }

    const topListingIds = recommendations
      .map((listing) => listing?.listing_id)
      .filter(Boolean)
      .slice(0, 20);

    const hasMlScores = recommendations.some((listing) => listing?.ml_score != null);

    return {
      client_session_id: swipeSessionIdRef.current,
      surface: 'discover',
      recommendation_count_shown: recommendations.length,
      top_listing_ids_shown: topListingIds,
      algorithm_version: context?.algorithm_version ?? recommendations[0]?.algorithm_version ?? DISCOVER_ALGORITHM_VERSION,
      model_version: context?.model_version ?? (hasMlScores ? 'recommender-v1' : null),
      experiment_name: context?.experiment_name ?? (recommendations.length > 0 ? 'discover_ranker_v1' : null),
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
      const response = await fetch(`${API_BASE}/api/interactions/recommendation-events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
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
      });

      if (!response.ok && response.status !== 503) {
        console.warn('Failed to persist discover recommendation event');
      }
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken, feedbackSessionId]);

  const fetchRecommendations = useCallback(async ({ append = false } = {}) => {
    setLoading(true);
    setError(null);
    if (!append) setEmptyResultReason(null);
    if (!append && typeof window !== 'undefined') {
      swipeSessionIdRef.current = createRecommendationEventId('discover-session');
    }

    try {
      // Fetch user preferences
      let prefs = {};
      let hasCorePreferences = false;
      const swipedIds = new Set();
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
          setEmptyResultReason('missing_preferences');
          return;
        }

        try {
          const swipesRes = await fetch(`${API_BASE}/api/interactions/swipes/me?limit=500`, {
            headers: { Authorization: `Bearer ${authState.accessToken}` },
          });
          if (swipesRes.ok) {
            const swipesPayload = await swipesRes.json();
            for (const event of swipesPayload?.data || []) {
              if (event?.listing_id) swipedIds.add(event.listing_id);
            }
          }
        } catch {
          // Swipe history fetch is optional; fall back to local liked cache only.
        }
      }

      // Build liked-listing averages to personalise the model
      const liked = getLikedListings();
      const likedExtras = {};
      let behaviorSampleSize;

      // Prefer persisted behavior features from backend (Phase 2A).
      if (authState?.accessToken) {
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
          // Behavior vector is optional in Phase 2A.
        }
      }

      // Fallback to local in-session liked cache when backend behavior data is sparse.
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
        offset: append ? nextOffsetRef.current : 0,
        behavior_sample_size: behaviorSampleSize,
        ...likedExtras,
      };

      // Cache the filter body so swipe-context events can reference it.
      activeFilterBodyRef.current = body;

      const res = await fetch(`${API_BASE}/api/recommendations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      const nextRankingContext = deriveRankingContext(data);
      setRankingContext(nextRankingContext);

      // Filter out listings already seen via swipes or saved likes.
      const likedIds = new Set(getLikedListings().map((l) => l.listing_id));
      const fresh = (data.recommendations || []).filter(
        (l) => !likedIds.has(l.listing_id) && !swipedIds.has(l.listing_id)
      );

      setHasMore(Boolean(data.has_more));
      nextOffsetRef.current = (data.offset || 0) + (data.count || 0);

      // Fire search query event — demand intelligence, best-effort.
      if (authState?.accessToken) {
        void persistSearchQueryEvent({
          filterBody: body,
          resultsCount: (data.recommendations || []).length,
          searchOffset: body.offset || 0,
        });
      }

      if (append) {
        setListings((prev) => [...prev, ...fresh]);
      } else {
        setListings(fresh);
        setCurrentIndex(0);
        sessionMetricsRef.current = { likesCount: 0, detailOpensCount: 0, swipesCount: 0 };
        promptShownRef.current = false;
        setFeedbackSessionId(null);
        setPromptAllowed(false);
        setShowFeedbackPrompt(false);
        setFeedbackStep('question');
        setPendingFeedbackLabel(null);
        setFeedbackAcknowledged(false);
        surfaceStartedAtRef.current = Date.now();
        setEmptyResultReason(
          fresh.length === 0
            ? (hasCorePreferences ? 'strict_constraints' : 'missing_preferences')
            : null
        );
        nextOffsetRef.current = (data.offset || 0) + (data.count || 0);
      }
    } catch (err) {
      setError(normalizeRecommendationsError(err));
    } finally {
      setLoading(false);
    }
  }, [userId, authState?.accessToken]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  useEffect(() => {
    latestSessionIdRef.current = feedbackSessionId;
  }, [feedbackSessionId]);

  useEffect(() => {
    latestTokenRef.current = authState?.accessToken ?? null;
  }, [authState?.accessToken]);

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
        if (!swipeSessionIdRef.current) {
          swipeSessionIdRef.current = getOrCreateSwipeSessionId();
        }

        const response = await fetch(`${API_BASE}/api/interactions/recommendation-sessions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authState.accessToken}`,
          },
          body: JSON.stringify(buildSessionPayload(listings, rankingContext)),
        });

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
  }, [authState?.accessToken, buildSessionPayload, error, listings, loading, rankingContext, userId]);

  useEffect(() => {
    if (
      promptShownRef.current ||
      !feedbackSessionId ||
      !promptAllowed ||
      showFeedbackPrompt ||
      feedbackSubmitting ||
      loading ||
      error ||
      currentIndex < DISCOVER_FEEDBACK_SWIPE_THRESHOLD
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
    currentIndex,
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
          likes_count: sessionMetricsRef.current.likesCount,
          detail_opens_count: sessionMetricsRef.current.detailOpensCount,
          recommendation_count_shown: recommendations.length,
          top_listing_ids_shown: topListingIds,
          algorithm_version: context?.algorithm_version ?? DISCOVER_ALGORITHM_VERSION,
          model_version: context?.model_version ?? (recommendations.some((listing) => listing?.ml_score != null) ? 'recommender-v1' : null),
          experiment_name: context?.experiment_name ?? (recommendations.length > 0 ? 'discover_ranker_v1' : null),
          experiment_variant: context?.experiment_variant ?? (recommendations.length > 0 ? (recommendations.some((listing) => listing?.ml_score != null) ? 'two_tower' : 'baseline') : null),
        }),
        keepalive: true,
      }).catch(() => {});
    };
  }, []);


  useEffect(() => {
    setExpandedImageIndex(0);
  }, [expandedListing?.listing_id]);

  useEffect(() => {
    const remaining = listings.length - currentIndex;
    if (!loading && !error && hasMore && remaining === 0) {
      fetchRecommendations({ append: true });
    }
  }, [currentIndex, listings.length, loading, error, hasMore, fetchRecommendations]);

  const persistSwipeEvent = useCallback(async ({ listing, action, position, startedAt }) => {
    if (!authState?.accessToken || !userId || !listing?.listing_id) return;

    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }

    const algorithmVersion =
      listing?.algorithm_version != null && String(listing.algorithm_version).trim()
        ? String(listing.algorithm_version).trim()
        : DISCOVER_ALGORITHM_VERSION;

    try {
      const response = await fetch(`${API_BASE}/api/interactions/swipes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authState.accessToken}`,
        },
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
      });

      // Do not disrupt UX on telemetry failures.
      if (!response.ok && response.status !== 503) {
        console.warn('Failed to persist swipe interaction');
      }
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken, userId]);

  const persistSwipeContextEvent = useCallback(async ({ listing, action }) => {
    if (!authState?.accessToken || !listing?.listing_id) return;
    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }
    try {
      await fetch(`${API_BASE}/api/interactions/swipe-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authState.accessToken}` },
        body: JSON.stringify({
          listing_id: listing.listing_id,
          action,
          session_id: swipeSessionIdRef.current,
          active_filters_snapshot: activeFilterBodyRef.current || null,
          device_context: collectDeviceContext(),
        }),
      });
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
      await fetch(`${API_BASE}/api/interactions/listing-views`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authState.accessToken}` },
        body: JSON.stringify({
          listing_id: listing.listing_id,
          surface,
          session_id: swipeSessionIdRef.current,
          view_duration_ms: duration_ms,
          expanded: cardExpandedRef.current,
          photos_viewed_count: cardPhotoCountRef.current,
        }),
      });
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken]);

  const persistSearchQueryEvent = useCallback(async ({ filterBody, resultsCount, searchOffset }) => {
    if (!authState?.accessToken) return;
    if (!swipeSessionIdRef.current) {
      swipeSessionIdRef.current = getOrCreateSwipeSessionId();
    }
    try {
      await fetch(`${API_BASE}/api/interactions/search-queries`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authState.accessToken}` },
        body: JSON.stringify({
          session_id: swipeSessionIdRef.current,
          filter_snapshot: filterBody,
          results_returned: resultsCount,
          offset: searchOffset,
        }),
      });
    } catch {
      // Best-effort only.
    }
  }, [authState?.accessToken]);

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
        console.warn('Failed to submit discover recommendation feedback');
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
  }, [
    authState?.accessToken,
    feedbackSessionId,
    feedbackSubmitting,
    listings,
    patchRecommendationSession,
    rankingContext,
  ]);

  const dismissFeedbackPrompt = useCallback(async () => {
    setShowFeedbackPrompt(false);
    setPromptAllowed(false);
    setFeedbackStep('question');
    setPendingFeedbackLabel(null);
    await patchRecommendationSession({
      prompt_dismissed: true,
      likes_count: sessionMetricsRef.current.likesCount,
      detail_opens_count: sessionMetricsRef.current.detailOpensCount,
      surface_dwell_ms: Math.max(0, Date.now() - surfaceStartedAtRef.current),
    });
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

  // Reset view-tracking refs whenever the top card changes.
  useEffect(() => {
    if (listings.length === 0 || currentIndex >= listings.length) return;
    cardViewStartRef.current = Date.now();
    cardPhotoCountRef.current = 0;
    cardExpandedRef.current = false;
  }, [currentIndex, listings.length]);

  const handleSwipe = useCallback((direction, listing) => {
    const action = direction === 'right' ? 'like' : 'pass';
    if (action === 'like') saveLikedListing(listing);

    // Feed position must match the card index in this session's stack (0-based).
    const top = listings[currentIndex];
    const position =
      top && listing?.listing_id === top.listing_id
        ? currentIndex
        : listings.findIndex((item) => item.listing_id === listing?.listing_id);
    const startedAt = typeof performance !== 'undefined' ? performance.now() : null;

    // Fire data logging events before advancing the index (best-effort, parallel).
    void persistListingViewEvent({ listing, surface: 'discover_card' });
    void persistSwipeContextEvent({ listing, action });

    void persistSwipeEvent({
      listing,
      action,
      position: position >= 0 ? position : currentIndex,
      startedAt,
    });

    sessionMetricsRef.current.swipesCount += 1;
    if (action === 'like') {
      sessionMetricsRef.current.likesCount += 1;
    }

    setCurrentIndex((prev) => prev + 1);

    if (tourPhase === 'discover') {
      window.dispatchEvent(new CustomEvent('padly-tour-swipe', {
        detail: { direction },
      }));
    }
  }, [currentIndex, listings, persistSwipeEvent, persistListingViewEvent, persistSwipeContextEvent, tourPhase]);

  const handleButton = (direction) => {
    if (currentIndex >= listings.length) return;
    handleSwipe(direction, listings[currentIndex]);
  };

  const handleModalAction = (direction) => {
    closeExpanded();
    setTimeout(() => handleButton(direction), 200);
  };


  const openExpanded = (listing) => {
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
  };

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
        </Stack>

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
          {loading && (
            <Stack align="center" gap="md" style={{ height: 520, justifyContent: 'center' }}>
              <Loader size="lg" color="#20c997" />
              <Text c="dimmed">Finding listings for you…</Text>
            </Stack>
          )}

          {/* Error */}
          {!loading && error && (
            <Stack align="center" gap="md" style={{ height: 520, justifyContent: 'center' }}>
              <Text c="red">{error}</Text>
              <Button onClick={fetchRecommendations} variant="light" color="teal">
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
                  onClick={fetchRecommendations}
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
                  onClick={fetchRecommendations}
                  color="teal"
                >
                  Reload
                </Button>
                <Button variant="light" color="teal" onClick={() => router.push('/matches')}>
                  View Matches
                </Button>
                <Button variant="outline" color="teal" onClick={() => router.push('/roommates')}>
                  Find roommate matches
                </Button>
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

          const amenities = expandedListing.amenities && typeof expandedListing.amenities === 'object'
            ? expandedListing.amenities
            : {};

          const bedsLabel = expandedListing.number_of_bedrooms === 0
            ? 'Studio'
            : expandedListing.number_of_bedrooms != null
              ? String(expandedListing.number_of_bedrooms)
              : '—';

          return (
            <Box>
              {/* Hero image */}
              <Box style={{ position: 'relative', height: 300, overflow: 'hidden', borderRadius: '12px 12px 0 0' }}>
                <ImageWithFallback
                  src={heroImage}
                  alt={expandedListing.title || 'Listing'}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />

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
                    {expandedListing.title || 'Listing'}
                  </Text>
                  {expandedListing.city && (
                    <Text size="sm" style={{ color: 'rgba(255,255,255,0.80)', marginTop: 2 }}>
                      {expandedListing.city}
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
                      key={`${expandedListing.listing_id || expandedListing.title || 'listing'}-${index}`}
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
                        alt={`${expandedListing.title || 'Listing'} ${index + 1}`}
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
                      {expandedListing.property_type}
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
                      <Text size="sm">{expandedListing.lease_type}</Text>
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
                {Object.entries(amenities).filter(([, v]) => v).length > 0 && (
                  <Group gap="xs" mb="md" wrap="wrap">
                    {Object.entries(amenities)
                      .filter(([, v]) => v)
                      .map(([key]) => (
                        <Badge key={key} variant="light" color="teal" size="sm" radius="sm">
                          {key}
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

    </Box>
  );
}
