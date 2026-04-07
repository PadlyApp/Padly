import { createAppError, parseApiErrorResponse } from './errorHandling';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function throwApiError(response, fallbackMessage = 'Request failed') {
  const info = await parseApiErrorResponse(response, fallbackMessage);
  throw createAppError(info.message, {
    status: info.status,
    payload: info.payload,
    rawMessage: info.message,
  });
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
    const url = `${API_BASE_URL}/api/listings${queryString ? `?${queryString}` : ''}`;
    
    const response = await fetch(url);
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch listings');
    }
    const data = await response.json();
    return data;
  },

  async getListing(id) {
    const response = await fetch(`${API_BASE_URL}/api/listings/${id}`);
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch listing');
    }
    const data = await response.json();
    return data;
  },

  async getInterestedListings(token) {
    const response = await fetch(`${API_BASE_URL}/api/interactions/interested-listings`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch interested listings');
    }
    return response.json();
  },

  async getInterestedListingIds(token) {
    const response = await fetch(`${API_BASE_URL}/api/interactions/interested-listings/ids`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch interested listing ids');
    }
    return response.json();
  },

  async markInterestedListing(token, listingId, source = null) {
    const response = await fetch(`${API_BASE_URL}/api/interactions/interested-listings/${listingId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ source }),
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to mark listing interested');
    }
    return response.json();
  },

  async unmarkInterestedListing(token, listingId) {
    const response = await fetch(`${API_BASE_URL}/api/interactions/interested-listings/${listingId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to remove interested listing');
    }
    return response.json();
  },

  async createListing(listingData, token) {
    const response = await fetch(`${API_BASE_URL}/api/listings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(listingData),
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to create listing');
    }
    const data = await response.json();
    return data;
  },

  // Users endpoints
  async getUsers(token, limit = 100, offset = 0) {
    const response = await fetch(`${API_BASE_URL}/api/users?limit=${limit}&offset=${offset}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch users');
    }
    const data = await response.json();
    return data;
  },

  async searchUsers(token, options = {}) {
    const params = new URLSearchParams();
    params.append('limit', String(options.limit ?? 20));
    params.append('offset', String(options.offset ?? 0));
    const q = (options.q || '').trim();
    if (q) params.append('q', q);

    const response = await fetch(`${API_BASE_URL}/api/users?${params.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to search users');
    }
    return response.json();
  },

  async getUser(id, token) {
    const response = await fetch(`${API_BASE_URL}/api/users/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch user');
    }
    const data = await response.json();
    return data;
  },

  /** Authenticated user profile fetch (for inbox name resolution). */
  async getUserWithAuth(id, token) {
    const response = await fetch(`${API_BASE_URL}/api/users/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch user');
    }
    return response.json();
  },

  /** Roommate suggestions; requires target_city on seeker prefs. */
  async getRoommateSuggestions(token, options = {}) {
    const params = new URLSearchParams();
    const limit = options.limit ?? 20;
    params.append('limit', String(limit));
    const mode = options.mode === 'hard_filter' ? 'hard_filter' : 'ml';
    params.append('mode', mode);
    const response = await fetch(
      `${API_BASE_URL}/api/matches/roommate-suggestions?${params.toString()}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch roommate suggestions');
    }
    return response.json();
  },

  async expressRoommateInterest(token, toUserId) {
    const response = await fetch(`${API_BASE_URL}/api/roommate-intros/express-interest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ to_user_id: toUserId }),
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to send roommate interest');
    }
    return response.json();
  },

  async getRoommateIntroInbox(token) {
    const response = await fetch(`${API_BASE_URL}/api/roommate-intros/inbox`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch roommate inbox');
    }
    return response.json();
  },

  async respondToRoommateIntro(token, introId, action) {
    const response = await fetch(
      `${API_BASE_URL}/api/roommate-intros/${encodeURIComponent(introId)}/respond`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ action }),
      }
    );
    if (!response.ok) {
      await throwApiError(response, 'Failed to respond to roommate intro');
    }
    return response.json();
  },

  async getIntroStatusWith(token, otherUserId) {
    const response = await fetch(
      `${API_BASE_URL}/api/roommate-intros/status-with/${encodeURIComponent(otherUserId)}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch intro status');
    }
    return response.json();
  },

  async createUser(userData, token) {
    const response = await fetch(`${API_BASE_URL}/api/users`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: JSON.stringify(userData),
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to create user');
    }
    const data = await response.json();
    return data;
  },

  // Roommate posts endpoints
  async getRoommatePosts(filters = {}) {
    const params = new URLSearchParams();
    
    if (filters.status) params.append('status', filters.status);
    if (filters.city) params.append('city', filters.city);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);
    
    const queryString = params.toString();
    const url = `${API_BASE_URL}/api/roommate-posts${queryString ? `?${queryString}` : ''}`;
    
    const response = await fetch(url);
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch roommate posts');
    }
    const data = await response.json();
    return data;
  },

  async getRoommatePost(id) {
    const response = await fetch(`${API_BASE_URL}/api/roommate-posts/${id}`);
    if (!response.ok) {
      await throwApiError(response, 'Failed to fetch roommate post');
    }
    const data = await response.json();
    return data;
  },

  async createRoommatePost(postData, token) {
    const response = await fetch(`${API_BASE_URL}/api/roommate-posts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(postData),
    });
    if (!response.ok) {
      await throwApiError(response, 'Failed to create roommate post');
    }
    const data = await response.json();
    return data;
  },

  // ---------------------------------------------------------------------------
  // Data logging — all four are best-effort. Callers should not await or handle
  // errors from these; tracking failures must never disrupt UX.
  // ---------------------------------------------------------------------------

  async postSwipeContext(token, payload) {
    try {
      await fetch(`${API_BASE_URL}/api/interactions/swipe-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
    } catch {
      // Best-effort only.
    }
  },

  async postListingView(token, payload) {
    try {
      await fetch(`${API_BASE_URL}/api/interactions/listing-views`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
    } catch {
      // Best-effort only.
    }
  },

  async postPageView(token, payload) {
    try {
      await fetch(`${API_BASE_URL}/api/interactions/page-views`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
    } catch {
      // Best-effort only.
    }
  },

  async postSearchQuery(token, payload) {
    try {
      await fetch(`${API_BASE_URL}/api/interactions/search-queries`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
    } catch {
      // Best-effort only.
    }
  },
};
