// Updated auth service to communicate with FastAPI backend
import {
  createAppError,
  normalizeAuthErrorMessage,
  parseApiErrorResponse,
} from './errorHandling';
import { apiUrl } from './api';
import { supabase } from './supabaseClient';

export class AuthService {
  static async signup(email, password, fullName) {
    try {
      const response = await fetch(apiUrl('/auth/signup'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
        }),
      });

      if (response.status === 202) {
        const info = await parseApiErrorResponse(
          response,
          'Account created. Please check your email to confirm your account.'
        );
        throw createAppError(info.message, {
          status: 202,
          code: 'EMAIL_CONFIRMATION_REQUIRED',
          payload: info.payload,
        });
      }

      if (!response.ok) {
        const info = await parseApiErrorResponse(response, 'Signup failed');
        throw createAppError(normalizeAuthErrorMessage(info, { flow: 'signup' }), {
          status: info.status,
          payload: info.payload,
          rawMessage: info.message,
        });
      }

      return response.json();
    } catch (error) {
      if (error?.name === 'AppError') throw error;
      throw createAppError(normalizeAuthErrorMessage(error, { flow: 'signup' }), {
        isNetworkError: true,
      });
    }
  }

  static async signin(email, password) {
    try {
      const response = await fetch(apiUrl('/auth/signin'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (!response.ok) {
        const info = await parseApiErrorResponse(response, 'Signin failed');
        throw createAppError(normalizeAuthErrorMessage(info, { flow: 'signin' }), {
          status: info.status,
          payload: info.payload,
          rawMessage: info.message,
        });
      }

      return response.json();
    } catch (error) {
      if (error?.name === 'AppError') throw error;
      throw createAppError(normalizeAuthErrorMessage(error, { flow: 'signin' }), {
        isNetworkError: true,
      });
    }
  }

  static async signout(token) {
    try {
      const response = await fetch(apiUrl('/auth/signout'), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const info = await parseApiErrorResponse(response, 'Signout failed');
        throw createAppError(info.message, { status: info.status, payload: info.payload });
      }

      return response.json();
    } catch (error) {
      if (error?.name === 'AppError') throw error;
      throw createAppError("Couldn't sign you out right now. Please try again.", {
        isNetworkError: true,
      });
    }
  }

  static async getCurrentUser(token) {
    try {
      const response = await fetch(apiUrl('/auth/me'), {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const info = await parseApiErrorResponse(response, 'Failed to get user');
        throw createAppError(info.message, { status: info.status, payload: info.payload });
      }

      return response.json();
    } catch (error) {
      if (error?.name === 'AppError') throw error;
      throw createAppError("Couldn't load your account right now. Please try again.", {
        isNetworkError: true,
      });
    }
  }

  static async signInWithGoogle(redirectTo) {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo },
    });
    if (error) throw createAppError(error.message, { isNetworkError: false });
  }

  static async refreshToken(refreshToken) {
    try {
      const response = await fetch(apiUrl('/auth/refresh'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        const info = await parseApiErrorResponse(response, 'Token refresh failed');
        throw createAppError(info.message, { status: info.status, payload: info.payload });
      }

      return response.json();
    } catch (error) {
      if (error?.name === 'AppError') throw error;
      throw createAppError("Couldn't refresh your session. Please sign in again.", {
        isNetworkError: true,
      });
    }
  }
}
