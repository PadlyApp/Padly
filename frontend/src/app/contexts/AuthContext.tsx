'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AuthService } from '../../../lib/authService';

interface User {
  id: string;
  email: string;
  profile?: {
    id: string;
    full_name: string;
    bio?: string;
    profile_picture_url?: string;
    role: string;
    verification_status: string;
  };
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  expiresAt: number | null;
}

interface AuthContextType {
  user: User | null;
  authState: AuthState | null;
  isLoading: boolean;
  signup: (email: string, password: string, fullName: string) => Promise<void>;
  signin: (email: string, password: string) => Promise<void>;
  signout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = 'padly_auth';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authState, setAuthState] = useState<AuthState | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load auth state from localStorage on mount
  useEffect(() => {
    const loadAuthState = () => {
      try {
        const stored = localStorage.getItem(AUTH_STORAGE_KEY);
        if (stored) {
          const parsedAuth: AuthState = JSON.parse(stored);
          
          // Check if token is expired
          if (parsedAuth.expiresAt && Date.now() < parsedAuth.expiresAt) {
            setAuthState(parsedAuth);
            // Load user data
            loadCurrentUser(parsedAuth.accessToken);
          } else {
            // Token expired, try to refresh
            if (parsedAuth.refreshToken) {
              refreshAuthToken(parsedAuth.refreshToken);
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

  const saveAuthState = (authData: any) => {
    const expiresAt = Date.now() + (authData.expires_in * 1000);
    const newAuthState: AuthState = {
      accessToken: authData.access_token,
      refreshToken: authData.refresh_token,
      expiresAt,
    };
    
    setAuthState(newAuthState);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(newAuthState));
  };

  const clearAuthState = () => {
    setUser(null);
    setAuthState(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
  };

  const loadCurrentUser = async (token: string | null) => {
    if (!token) return;
    
    try {
      const response = await AuthService.getCurrentUser(token);
      setUser(response.user);
    } catch (error) {
      console.error('Failed to load current user:', error);
      clearAuthState();
    }
  };

  const refreshAuthToken = async (refreshToken: string) => {
    try {
      const response = await AuthService.refreshToken(refreshToken);
      saveAuthState(response);
      loadCurrentUser(response.access_token);
    } catch (error) {
      console.error('Token refresh failed:', error);
      clearAuthState();
    }
  };

  const signup = async (email: string, password: string, fullName: string) => {
    try {
      const response = await AuthService.signup(email, password, fullName);
      saveAuthState(response);
      setUser(response.user);
    } catch (error) {
      throw error;
    }
  };

  const signin = async (email: string, password: string) => {
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
  return context;
}

// Hook to get authorization header for API requests
export function useAuthHeader() {
  const { authState } = useAuth();
  
  return authState?.accessToken ? {
    'Authorization': `Bearer ${authState.accessToken}`
  } : {};
}