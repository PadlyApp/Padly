// Updated auth service to communicate with FastAPI backend
export class AuthService {
  private static readonly API_BASE = 'http://localhost:8000/api/auth';

  static async signup(email: string, password: string, fullName: string) {
    const response = await fetch(`${this.API_BASE}/signup`, {
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

    const data = await response.json();

    if (response.status === 202) {
      // Email confirmation required
      throw new Error(data.message || 'Please check your email to confirm your account');
    }

    if (!response.ok) {
      throw new Error(data.detail || 'Signup failed');
    }

    return data;
  }

  static async signin(email: string, password: string) {
    const response = await fetch(`${this.API_BASE}/signin`, {
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
      const error = await response.json();
      throw new Error(error.detail || 'Signin failed');
    }

    return response.json();
  }

  static async signout(token: string) {
    const response = await fetch(`${this.API_BASE}/signout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Signout failed');
    }

    return response.json();
  }

  static async getCurrentUser(token: string) {
    const response = await fetch(`${this.API_BASE}/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get user');
    }

    return response.json();
  }

  static async refreshToken(refreshToken: string) {
    const response = await fetch(`${this.API_BASE}/refresh`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${refreshToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Token refresh failed');
    }

    return response.json();
  }
}