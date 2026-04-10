export const MATCHES_SCROLL_TRIGGER_PX = 900;
export const MATCHES_TOP_RETURN_PX = 120;
// How long a cached recommendations result stays fresh in localStorage.
// Matches the React Query staleTime so the two layers agree on freshness.
export const FEED_CACHE_TTL_MS = 5 * 60 * 1000;
// Cooldown a user must wait before manually retrying after an error (seconds).
export const RETRY_COOLDOWN_SECONDS = 60;
