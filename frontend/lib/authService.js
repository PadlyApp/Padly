// Updated auth service to communicate with FastAPI backend
export class AuthService {
  static API_BASE = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth`;

  static async signup(email, password, fullName) {
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

  static async signin(email, password) {
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

  static async signout(token) {
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

  static async getCurrentUser(token) {
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

  static async refreshToken(refreshToken) {
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
