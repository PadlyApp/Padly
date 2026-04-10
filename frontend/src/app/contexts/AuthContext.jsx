'use client';

import { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
 *   signInWithGoogle: () => Promise<void>,
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
  const refreshPromiseRef = useRef(null);
  const sessionVersionRef = useRef(0);

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

    // Set a lightweight session cookie so Next.js middleware can detect auth
    // without touching the actual JWT. SameSite=Lax blocks cross-site POSTs.
    document.cookie = `padly_session=1; path=/; SameSite=Lax`;

    // Save user data if present
    if (authData.user) {
      setUser(authData.user);
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(authData.user));
    }
  };

  const clearAuthState = () => {
    sessionVersionRef.current += 1;
    setUser(null);
    setAuthState(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
    // Clear the session cookie
    document.cookie = 'padly_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';
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

  const refreshAuthToken = useCallback(async (token) => {
    // If a refresh is already in flight, reuse the same promise to avoid
    // concurrent calls burning the single-use Supabase refresh token.
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    // Capture the session version before the async call so we can detect
    // a signout that happens while the refresh is in-flight.
    const sessionAtStart = sessionVersionRef.current;

    refreshPromiseRef.current = (async () => {
      try {
        const response = await AuthService.refreshToken(token);
        // If the user signed out while the refresh was in-flight, discard the
        // result to avoid re-authenticating an already-signed-out session.
        if (sessionVersionRef.current !== sessionAtStart) {
          return null;
        }
        saveAuthState(response);
        await loadCurrentUser(response.access_token);
        return response.access_token;
      } catch (error) {
        console.error('Token refresh failed:', error);
        clearAuthState();
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    return refreshPromiseRef.current;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- saveAuthState/loadCurrentUser/clearAuthState are stable non-memoized helpers; sessionVersionRef/refreshPromiseRef are refs that never change identity

  // Get a valid access token, refreshing if needed
  const getValidToken = useCallback(async () => {
    if (!authState) return null;

    const bufferTime = 60 * 1000;
    const isExpired = authState.expiresAt && Date.now() >= (authState.expiresAt - bufferTime);

    if (isExpired && authState.refreshToken) {
      return refreshAuthToken(authState.refreshToken);
    }

    return authState.accessToken;
  }, [authState, refreshAuthToken]);

  const signup = async (email, password, fullName) => {
    try {
      const response = await AuthService.signup(email, password, fullName);
      // saveAuthState persists tokens; then loadCurrentUser overwrites the user
      // with the canonical /me shape (user.profile.id etc.) that the rest of
      // the app expects — the raw /signup response has a different structure.
      saveAuthState(response);
      if (response.access_token) {
        await loadCurrentUser(response.access_token);
      }
      return response;
    } catch (error) {
      throw error;
    }
  };

  const signin = async (email, password) => {
    try {
      const response = await AuthService.signin(email, password);
      saveAuthState(response);
      setUser(response.user);
      return response;
    } catch (error) {
      throw error;
    }
  };

  const signInWithGoogle = async () => {
    const redirectTo = `${window.location.origin}/auth/callback`;
    await AuthService.signInWithGoogle(redirectTo);
    // No state change here — the /auth/callback page handles session persistence after the redirect
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

  const contextValue = useMemo(() => ({
    user,
    authState,
    isLoading,
    signup,
    signin,
    signout,
    signInWithGoogle,
    isAuthenticated,
    getValidToken,
  }), [user, authState, isLoading, isAuthenticated, getValidToken]); // eslint-disable-line react-hooks/exhaustive-deps -- signup/signin/signout/signInWithGoogle are stable non-memoized helpers

  return (
    <AuthContext.Provider value={contextValue}>
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

// Hook that returns an async function to get a fresh Authorization header.
// Always calls getValidToken() so expired tokens are refreshed automatically.
export function useAuthHeader() {
  const { getValidToken } = useAuth();
  return useCallback(async () => {
    const token = await getValidToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [getValidToken]);
}
