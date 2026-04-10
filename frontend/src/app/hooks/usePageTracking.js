'use client';

import { useEffect, useRef } from 'react';
import { apiFetch } from '../../../lib/api';

const SESSION_KEY = 'padly_swipe_session_id';

function getSessionId() {
  if (typeof window === 'undefined') return 'ssr-session';
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const id =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  sessionStorage.setItem(SESSION_KEY, id);
  return id;
}

/**
 * Tracks how long an authenticated user spends on a page.
 *
 * On mount: records start time.
 * On unmount: fires POST /api/interactions/page-views with duration_ms via
 *   keepalive fetch so the request survives component unmount / navigation.
 *
 * @param {string} pageName       - Must match the CHECK constraint in page_view_events
 *                                  (discover | matches | listing_detail | preferences |
 *                                   account | groups | roommates | onboarding)
 * @param {string|null} token     - User's JWT access token (from useAuth).
 *                                  If falsy, no event is fired.
 * @param {string|null} referrer  - Optional previous page name.
 */
export function usePageTracking(pageName, token, referrer = null) {
  const startRef = useRef(null);
  const sessionRef = useRef(null);

  useEffect(() => {
    if (!token) return;

    startRef.current = Date.now();
    sessionRef.current = getSessionId();

    return () => {
      const duration_ms =
        startRef.current != null ? Math.max(0, Date.now() - startRef.current) : null;

      const payload = JSON.stringify({
        page: pageName,
        session_id: sessionRef.current,
        duration_ms,
        referrer_page: referrer || null,
      });

      // keepalive: true lets the fetch outlive the component unmount.
      // We use fetch (not sendBeacon) because sendBeacon can't carry Authorization headers.
      apiFetch(
        `/interactions/page-views`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
          keepalive: true,
        },
        { token }
      ).catch(() => {
        // Best-effort only — swallow silently.
      });
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
}
