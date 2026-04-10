/** @typedef {Record<string, unknown>} GuestPrefs */

export const DISCOVER_FEEDBACK_SWIPE_THRESHOLD = 10;
export const DISCOVER_PROGRESS_TTL_MS = 30 * 60 * 1000;
export const SWIPE_SESSION_KEY = 'padly_swipe_session_id';

/** Stable client label for swipe telemetry (backend requires algorithm_version). */
export const DISCOVER_ALGORITHM_VERSION = 'discover-v1';

export function getDiscoverProgressKey(userId) {
  return `padly_discover_progress:${userId}`;
}

export function clearDiscoverProgress(userId) {
  if (typeof window === 'undefined' || !userId) return;

  try {
    sessionStorage.removeItem(getDiscoverProgressKey(userId));
  } catch {
    // Best-effort only.
  }
}

export function loadDiscoverProgress(userId) {
  if (typeof window === 'undefined' || !userId) return null;

  try {
    const raw = sessionStorage.getItem(getDiscoverProgressKey(userId));
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (!parsed?.savedAt || Date.now() - parsed.savedAt > DISCOVER_PROGRESS_TTL_MS) {
      sessionStorage.removeItem(getDiscoverProgressKey(userId));
      return null;
    }

    const hasListings = Array.isArray(parsed.listings) && parsed.listings.length > 0;
    const hasProgress = hasListings && Number.isFinite(parsed.currentIndex) && parsed.currentIndex > 0;
    const isCompletedStack =
      hasListings && Number.isFinite(parsed.currentIndex) && parsed.currentIndex >= parsed.listings.length;
    if (!hasProgress && !isCompletedStack) {
      sessionStorage.removeItem(getDiscoverProgressKey(userId));
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}

export function saveDiscoverProgress(userId, payload) {
  if (typeof window === 'undefined' || !userId) return;

  try {
    sessionStorage.setItem(
      getDiscoverProgressKey(userId),
      JSON.stringify({
        ...payload,
        savedAt: Date.now(),
      })
    );
  } catch {
    // Best-effort only.
  }
}

export function getOrCreateSwipeSessionId() {
  if (typeof window === 'undefined') return 'server-session';
  const existing = sessionStorage.getItem(SWIPE_SESSION_KEY);
  if (existing) return existing;

  const generated =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  sessionStorage.setItem(SWIPE_SESSION_KEY, generated);
  return generated;
}

export function collectDeviceContext() {
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
