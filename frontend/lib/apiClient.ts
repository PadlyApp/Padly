// API client for making authenticated requests to FastAPI backend
import { useAuthHeader } from '../src/app/contexts/AuthContext';

export class ApiClient {
  private static readonly BASE_URL = 'http://localhost:8000/api';

  static async request<T>(
    endpoint: string, 
    options: RequestInit = {},
    authHeader: Record<string, string> = {}
  ): Promise<T> {
    const url = `${this.BASE_URL}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Users API
  static async getUsers(authHeader: Record<string, string> = {}, limit = 100, offset = 0) {
    return this.request(`/users?limit=${limit}&offset=${offset}`, { method: 'GET' }, authHeader);
  }

  static async getUser(userId: string, authHeader: Record<string, string> = {}) {
    return this.request(`/users/${userId}`, { method: 'GET' }, authHeader);
  }

  static async createUser(userData: any, authHeader: Record<string, string> = {}) {
    return this.request('/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    }, authHeader);
  }

  static async updateUser(userId: string, userData: any, authHeader: Record<string, string> = {}) {
    return this.request(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    }, authHeader);
  }

  // Listings API
  static async getListings(authHeader: Record<string, string> = {}, limit = 100, offset = 0) {
    return this.request(`/listings?limit=${limit}&offset=${offset}`, { method: 'GET' }, authHeader);
  }

  static async getListing(listingId: string, authHeader: Record<string, string> = {}) {
    return this.request(`/listings/${listingId}`, { method: 'GET' }, authHeader);
  }

  static async createListing(listingData: any, authHeader: Record<string, string> = {}) {
    return this.request('/listings', {
      method: 'POST',
      body: JSON.stringify(listingData),
    }, authHeader);
  }

  static async updateListing(listingId: string, listingData: any, authHeader: Record<string, string> = {}) {
    return this.request(`/listings/${listingId}`, {
      method: 'PUT',
      body: JSON.stringify(listingData),
    }, authHeader);
  }
}

// React hook for authenticated API calls
export function useApiClient() {
  const authHeader = useAuthHeader();
  
  // Convert authHeader to proper Record<string, string> format
  const headers: Record<string, string> = {};
  if (authHeader.Authorization) {
    headers.Authorization = authHeader.Authorization;
  }
  
  return {
    // Users
    getUsers: (limit?: number, offset?: number) => 
      ApiClient.getUsers(headers, limit, offset),
    getUser: (userId: string) => 
      ApiClient.getUser(userId, headers),
    createUser: (userData: any) => 
      ApiClient.createUser(userData, headers),
    updateUser: (userId: string, userData: any) => 
      ApiClient.updateUser(userId, userData, headers),
    
    // Listings
    getListings: (limit?: number, offset?: number) => 
      ApiClient.getListings(headers, limit, offset),
    getListing: (listingId: string) => 
      ApiClient.getListing(listingId, headers),
    createListing: (listingData: any) => 
      ApiClient.createListing(listingData, headers),
    updateListing: (listingId: string, listingData: any) => 
      ApiClient.updateListing(listingId, listingData, headers),
  };
}