export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function parseFastApiDetail(payload) {
  const d = payload?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d
      .map((x) => (typeof x === 'string' ? x : x?.msg || JSON.stringify(x)))
      .join(', ');
  }
  return payload?.message || 'Request failed';
}

async function readApiError(response) {
  try {
    const j = await response.json();
    return parseFastApiDetail(j);
  } catch {
    return response.statusText || 'Request failed';
  }
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
      throw new Error('Failed to fetch listings');
    }
    const data = await response.json();
    return data;
  },

  async getListing(id) {
    const response = await fetch(`${API_BASE_URL}/api/listings/${id}`);
    if (!response.ok) {
      throw new Error('Failed to fetch listing');
    }
    const data = await response.json();
    return data;
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
      throw new Error('Failed to create listing');
    }
    const data = await response.json();
    return data;
  },

  // Users endpoints
  async getUsers(limit = 100, offset = 0) {
    const response = await fetch(`${API_BASE_URL}/api/users?limit=${limit}&offset=${offset}`);
    if (!response.ok) {
      throw new Error('Failed to fetch users');
    }
    const data = await response.json();
    return data;
  },

  async getUser(id) {
    const response = await fetch(`${API_BASE_URL}/api/users/${id}`);
    if (!response.ok) {
      throw new Error('Failed to fetch user');
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
      const msg = await readApiError(response);
      throw new Error(msg);
    }
    return response.json();
  },

  /** Ranked roommate suggestions (Phase 2); requires target_city on seeker prefs. */
  async getRoommateSuggestions(token, options = {}) {
    const params = new URLSearchParams();
    const limit = options.limit ?? 20;
    params.append('limit', String(limit));
    if (options.blendEmbedding) {
      params.append('blend_embedding', 'true');
    }
    const response = await fetch(
      `${API_BASE_URL}/api/matches/roommate-suggestions?${params.toString()}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) {
      throw new Error(await readApiError(response));
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
      throw new Error(await readApiError(response));
    }
    return response.json();
  },

  async getRoommateIntroInbox(token) {
    const response = await fetch(`${API_BASE_URL}/api/roommate-intros/inbox`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
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
      throw new Error(await readApiError(response));
    }
    return response.json();
  },

  async getIntroStatusWith(token, otherUserId) {
    const response = await fetch(
      `${API_BASE_URL}/api/roommate-intros/status-with/${encodeURIComponent(otherUserId)}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) {
      throw new Error(await readApiError(response));
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
      throw new Error('Failed to create user');
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
      throw new Error('Failed to fetch roommate posts');
    }
    const data = await response.json();
    return data;
  },

  async getRoommatePost(id) {
    const response = await fetch(`${API_BASE_URL}/api/roommate-posts/${id}`);
    if (!response.ok) {
      throw new Error('Failed to fetch roommate post');
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
      throw new Error('Failed to create roommate post');
    }
    const data = await response.json();
    return data;
  },
};

