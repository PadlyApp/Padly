'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { AuthService } from '../../../lib/authService';

/**
 * @typedef {{
 *   user: any,
 *   authState: { accessToken: string, refreshToken: string, expiresAt: number } | null,
 *   isLoading: boolean,
 *   isAuthenticated: boolean,
 *   signup: (email: string, password: string, fullName: string) => Promise<void>,
 *   signin: (email: string, password: string) => Promise<void>,
 *   signout: () => Promise<void>,
 *   getValidToken: () => Promise<string | null>,
 * }} AuthContextValue
 */

/** @type {import('react').Context<AuthContextValue | undefined>} */
const AuthContext = createContext(undefined);

const AUTH_STORAGE_KEY = 'padly_auth';
const USER_STORAGE_KEY = 'padly_user';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [authState, setAuthState] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load auth state from localStorage on mount
  useEffect(() => {
    const loadAuthState = async () => {
      try {
        const stored = localStorage.getItem(AUTH_STORAGE_KEY);
        const storedUser = localStorage.getItem(USER_STORAGE_KEY);
        
        if (stored) {
          const parsedAuth = JSON.parse(stored);
          
          // Check if token is expired
          if (parsedAuth.expiresAt && Date.now() < parsedAuth.expiresAt) {
            setAuthState(parsedAuth);
            
            // Load user from storage or fetch from API
            if (storedUser) {
              try {
                setUser(JSON.parse(storedUser));
              } catch (e) {
                console.error('Failed to parse stored user, fetching fresh:', e);
                await loadCurrentUser(parsedAuth.accessToken);
              }
            } else {
              // No stored user, fetch from API
              console.log('No stored user found, fetching from API...');
              await loadCurrentUser(parsedAuth.accessToken);
            }
          } else {
            // Token expired, try to refresh
            if (parsedAuth.refreshToken) {
              await refreshAuthToken(parsedAuth.refreshToken);
            } else {
              clearAuthState();
            }
          }
        }
      } catch (error) {
        console.error('Error loading auth state:', error);
        clearAuthState();
      } finally {
        setIsLoading(false);
      }
    };

    loadAuthState();
  }, []);

  const saveAuthState = (authData) => {
    const expiresAt = Date.now() + (authData.expires_in * 1000);
    const newAuthState = {
      accessToken: authData.access_token,
      refreshToken: authData.refresh_token,
      expiresAt,
    };
    
    setAuthState(newAuthState);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(newAuthState));
    
    // Save user data if present
    if (authData.user) {
      setUser(authData.user);
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(authData.user));
    }
  };

  const clearAuthState = () => {
    setUser(null);
    setAuthState(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
  };

  const loadCurrentUser = async (token) => {
    if (!token) return;
    
    try {
      const response = await AuthService.getCurrentUser(token);
      setUser(response.user);
      // Save user to localStorage for future page loads
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.user));
    } catch (error) {
      console.error('Failed to load current user:', error);
      clearAuthState();
    }
  };

  const refreshAuthToken = async (refreshToken) => {
    try {
      const response = await AuthService.refreshToken(refreshToken);
      saveAuthState(response);
      await loadCurrentUser(response.access_token);
      return response.access_token;
    } catch (error) {
      console.error('Token refresh failed:', error);
      clearAuthState();
      return null;
    }
  };

  // Get a valid access token, refreshing if needed
  const getValidToken = async () => {
    if (!authState) return null;
    
    // Check if token is expired or about to expire (within 60 seconds)
    const bufferTime = 60 * 1000; // 60 seconds buffer
    const isExpired = authState.expiresAt && Date.now() >= (authState.expiresAt - bufferTime);
    
    if (isExpired && authState.refreshToken) {
      console.log('Token expired or expiring soon, refreshing...');
      const newToken = await refreshAuthToken(authState.refreshToken);
      return newToken;
    }
    
    return authState.accessToken;
  };

  const signup = async (email, password, fullName) => {
    try {
      const response = await AuthService.signup(email, password, fullName);
      saveAuthState(response);
      setUser(response.user);
    } catch (error) {
      throw error;
    }
  };

  const signin = async (email, password) => {
    try {
      const response = await AuthService.signin(email, password);
      saveAuthState(response);
      setUser(response.user);
    } catch (error) {
      throw error;
    }
  };

  const signout = async () => {
    try {
      if (authState?.accessToken) {
        await AuthService.signout(authState.accessToken);
      }
    } catch (error) {
      console.error('Signout error:', error);
    } finally {
      clearAuthState();
    }
  };

  const isAuthenticated = !!(authState?.accessToken && user);

  return (
    <AuthContext.Provider value={{
      user,
      authState,
      isLoading,
      signup,
      signin,
      signout,
      isAuthenticated,
      getValidToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return /** @type {AuthContextValue} */ (context);
}

// Hook to get authorization header for API requests
export function useAuthHeader() {
  const { authState } = useAuth();
  
  return authState?.accessToken ? {
    'Authorization': `Bearer ${authState.accessToken}`
  } : {};
}
