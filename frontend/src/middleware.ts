import { NextRequest, NextResponse } from 'next/server';

// Routes that do NOT require authentication
const PUBLIC_PATHS = new Set([
  '/',
  '/login',
  '/signup',
  '/auth/callback',
  // Guest browsing: unauthenticated users can reach these pages.
  // Rate limiting and result capping are enforced server-side.
  '/discover',
  '/preferences-setup',
]);

// Prefixes that are always public (static assets, Next internals, API routes)
const PUBLIC_PREFIXES = ['/_next/', '/favicon', '/api/'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Always allow public prefixes (static assets, Next.js internals, API routes)
  if (PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return NextResponse.next();
  }

  // Always allow exact public paths
  if (PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  // Check for the lightweight session cookie set by AuthContext on login
  const hasSession = request.cookies.has('padly_session');

  if (!hasSession) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = '/login';
    // Preserve the original destination so we can redirect back after login
    loginUrl.searchParams.set('redirectTo', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on all routes except Next.js internals and static files
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
