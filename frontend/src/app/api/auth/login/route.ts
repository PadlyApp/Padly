import { NextRequest, NextResponse } from 'next/server';
import { findUserByEmail } from '../mockData';

export async function POST(request: NextRequest) {
  try {
    // Parse the request body
    const { email, password } = await request.json();

    // Validate input
    if (!email || !password) {
      return NextResponse.json(
        { error: 'Email and password are required' },
        { status: 400 }
      );
    }

    // Simulate API delay (like a real server)
    await new Promise(resolve => setTimeout(resolve, 500));

    // Find user in mock database
    const user = findUserByEmail(email);

    if (!user) {
      return NextResponse.json(
        { error: 'User not found' },
        { status: 404 }
      );
    }

    // Check password (in real apps, compare hashed passwords!)
    if (user.password !== password) {
      return NextResponse.json(
        { error: 'Invalid password' },
        { status: 401 }
      );
    }

    // Login successful - return user data (without password!)
    const { password: _, ...userWithoutPassword } = user;
    
    return NextResponse.json({
      message: 'Login successful',
      user: userWithoutPassword
    }, { status: 200 });

  } catch (error) {
    console.error('Login error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}