import { createAppError, parseApiErrorResponse } from './errorHandling';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Full URL for a path under `/api` (leading slash optional). */
export function apiUrl(pathAfterApi) {
  const p = String(pathAfterApi).startsWith('/') ? pathAfterApi : `/${pathAfterApi}`;
  return `${API_BASE_URL}/api${p}`;
}

export function mergeAuthHeaders(initHeaders, token) {
  const headers = new Headers(initHeaders ?? undefined);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return headers;
}

/**
 * `fetch` to the backend `/api/*` route.
 * @param {string} pathAfterApi e.g. `/preferences/abc` or `preferences/abc`
 * @param {RequestInit} [init]
 * @param {{ token?: string|null }} [extra]
 */
export function apiFetch(pathAfterApi, init = {}, extra = {}) {
  const { token } = extra;
  const headers = mergeAuthHeaders(init.headers, token);
  return fetch(apiUrl(pathAfterApi), { ...init, headers });
}

/**
 * JSON-oriented request with shared error normalization (throws AppError from errorHandling).
 * Pass `json` to stringify body and set Content-Type. Other RequestInit fields (signal, keepalive, etc.) are forwarded.
 */
export async function apiJson(pathAfterApi, options = {}) {
  const {
    method = 'GET',
    headers: hdrs,
    body,
    json,
    token,
    fallbackMessage = 'Request failed',
    ...fetchRest
  } = options;

  const headers = mergeAuthHeaders(hdrs, token);
  let finalBody = body;
  if (json !== undefined) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    finalBody = JSON.stringify(json);
  }

  const response = await fetch(apiUrl(pathAfterApi), {
    ...fetchRest,
    method,
    headers,
    body: finalBody,
  });

  if (!response.ok) {
    await throwApiError(response, fallbackMessage);
  }

  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function throwApiError(response, fallbackMessage = 'Request failed') {
  const info = await parseApiErrorResponse(response, fallbackMessage);
  throw createAppError(info.message, {
    status: info.status,
    payload: info.payload,
    rawMessage: info.message,
  });
}

async function readJsonOrThrow(response, fallbackMessage) {
  if (!response.ok) {
    await throwApiError(response, fallbackMessage);
  }
  return response.json();
}

export const api = {
  // Listings endpoints
  async getListings(filters = {}) {
    const params = new URLSearchParams();

    if (filters.status) params.append('status', filters.status);
    if (filters.city) params.append('city', filters.city);
    if (filters.property_type) params.append('property_type', filters.property_type);
    if (filters.min_price) params.append('min_price', filters.min_price);
    if (filters.max_price) params.append('max_price', filters.max_price);
    if (filters.min_bedrooms) params.append('min_bedrooms', filters.min_bedrooms);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);

    const queryString = params.toString();
    const response = await apiFetch(`/listings${queryString ? `?${queryString}` : ''}`);
    return readJsonOrThrow(response, 'Failed to fetch listings');
  },

  async getListing(id) {
    const response = await apiFetch(`/listings/${id}`);
    return readJsonOrThrow(response, 'Failed to fetch listing');
  },

  async getInterestedListings(token) {
    const response = await apiFetch('/interactions/interested-listings', {}, { token });
    return readJsonOrThrow(response, 'Failed to fetch interested listings');
  },

  async getInterestedListingIds(token) {
    const response = await apiFetch('/interactions/interested-listings/ids', {}, { token });
    return readJsonOrThrow(response, 'Failed to fetch interested listing ids');
  },

  async markInterestedListing(token, listingId, source = null) {
    const response = await apiFetch(
      `/interactions/interested-listings/${listingId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source }),
      },
      { token }
    );
    return readJsonOrThrow(response, 'Failed to mark listing interested');
  },

  async unmarkInterestedListing(token, listingId) {
    const response = await apiFetch(`/interactions/interested-listings/${listingId}`, { method: 'DELETE' }, { token });
    return readJsonOrThrow(response, 'Failed to remove interested listing');
  },

  async createListing(listingData, token) {
    const response = await apiFetch(
      '/listings',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(listingData),
      },
      { token }
    );
    return readJsonOrThrow(response, 'Failed to create listing');
  },

  // Users endpoints
  async getUsers(token, limit = 100, offset = 0) {
    const response = await apiFetch(`/users?limit=${limit}&offset=${offset}`, {}, { token });
    return readJsonOrThrow(response, 'Failed to fetch users');
  },

  async searchUsers(token, options = {}) {
    const params = new URLSearchParams();
    params.append('limit', String(options.limit ?? 20));
    params.append('offset', String(options.offset ?? 0));
    const q = (options.q || '').trim();
    if (q) params.append('q', q);

    const response = await apiFetch(`/users?${params.toString()}`, {}, { token });
    return readJsonOrThrow(response, 'Failed to search users');
  },

  async getUser(id, token) {
    const response = await apiFetch(`/users/${id}`, {}, { token });
    return readJsonOrThrow(response, 'Failed to fetch user');
  },

  /** Authenticated user profile fetch (for inbox name resolution). */
  async getUserWithAuth(id, token) {
    const response = await apiFetch(`/users/${id}`, {}, { token });
    return readJsonOrThrow(response, 'Failed to fetch user');
  },

  /** Roommate suggestions; requires target_city on seeker prefs. */
  async getRoommateSuggestions(token, options = {}) {
    const params = new URLSearchParams();
    const limit = options.limit ?? 20;
    params.append('limit', String(limit));
    const mode = options.mode === 'hard_filter' ? 'hard_filter' : 'ml';
    params.append('mode', mode);
    const response = await apiFetch(`/matches/roommate-suggestions?${params.toString()}`, {}, { token });
    return readJsonOrThrow(response, 'Failed to fetch roommate suggestions');
  },

  async expressRoommateInterest(token, toUserId) {
    const response = await apiFetch(
      '/roommate-intros/express-interest',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_user_id: toUserId }),
      },
      { token }
    );
    return readJsonOrThrow(response, 'Failed to send roommate interest');
  },

  async getRoommateIntroInbox(token) {
    const response = await apiFetch('/roommate-intros/inbox', {}, { token });
    return readJsonOrThrow(response, 'Failed to fetch roommate inbox');
  },

  async respondToRoommateIntro(token, introId, action) {
    const response = await apiFetch(
      `/roommate-intros/${encodeURIComponent(introId)}/respond`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      },
      { token }
    );
    return readJsonOrThrow(response, 'Failed to respond to roommate intro');
  },

  async getIntroStatusWith(token, otherUserId) {
    const response = await apiFetch(
      `/roommate-intros/status-with/${encodeURIComponent(otherUserId)}`,
      {},
      { token }
    );
    return readJsonOrThrow(response, 'Failed to fetch intro status');
  },

  async createUser(userData, token) {
    const headers = { 'Content-Type': 'application/json' };
    const response = await apiFetch(
      '/users',
      {
        method: 'POST',
        headers,
        body: JSON.stringify(userData),
      },
      { token }
    );
    return readJsonOrThrow(response, 'Failed to create user');
  },

  // Roommate posts endpoints
  async getRoommatePosts(filters = {}) {
    const params = new URLSearchParams();

    if (filters.status) params.append('status', filters.status);
    if (filters.city) params.append('city', filters.city);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);

    const queryString = params.toString();
    const response = await apiFetch(`/roommate-posts${queryString ? `?${queryString}` : ''}`);
    return readJsonOrThrow(response, 'Failed to fetch roommate posts');
  },

  async getRoommatePost(id) {
    const response = await apiFetch(`/roommate-posts/${id}`);
    return readJsonOrThrow(response, 'Failed to fetch roommate post');
  },

  async createRoommatePost(postData, token) {
    const response = await apiFetch(
      '/roommate-posts',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(postData),
      },
      { token }
    );
    return readJsonOrThrow(response, 'Failed to create roommate post');
  },

  // ---------------------------------------------------------------------------
  // Data logging — all four are best-effort. Callers should not await or handle
  // errors from these; tracking failures must never disrupt UX.
  // ---------------------------------------------------------------------------

  async postSwipeContext(token, payload) {
    try {
      await apiFetch(
        '/interactions/swipe-context',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        { token }
      );
    } catch {
      // Best-effort only.
    }
  },

  async postListingView(token, payload) {
    try {
      await apiFetch(
        '/interactions/listing-views',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        { token }
      );
    } catch {
      // Best-effort only.
    }
  },

  async postPageView(token, payload) {
    try {
      await apiFetch(
        '/interactions/page-views',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        { token }
      );
    } catch {
      // Best-effort only.
    }
  },

  async postSearchQuery(token, payload) {
    try {
      await apiFetch(
        '/interactions/search-queries',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        { token }
      );
    } catch {
      // Best-effort only.
    }
  },
};
