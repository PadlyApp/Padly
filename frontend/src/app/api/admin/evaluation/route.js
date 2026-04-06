import { NextResponse } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const dynamic = 'force-dynamic';

async function fetchCurrentUser(authorization) {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: authorization },
    cache: 'no-store',
  });

  const payload = await response.json().catch(() => null);
  return { response, payload };
}

export async function GET(request) {
  const authorization = request.headers.get('authorization');
  if (!authorization) {
    return NextResponse.json({ detail: 'Authorization required' }, { status: 401 });
  }

  const adminSecret = process.env.ADMIN_SECRET;
  if (!adminSecret) {
    return NextResponse.json(
      { detail: 'Admin evaluation proxy is disabled: ADMIN_SECRET is not configured.' },
      { status: 503 },
    );
  }

  const { response: meResponse, payload: mePayload } = await fetchCurrentUser(authorization);
  if (!meResponse.ok) {
    return NextResponse.json(
      { detail: mePayload?.detail || 'Unable to validate current user' },
      { status: meResponse.status || 401 },
    );
  }

  const role = mePayload?.user?.profile?.role;
  if (role !== 'admin') {
    return NextResponse.json({ detail: 'Admin access required' }, { status: 403 });
  }

  const upstreamUrl = new URL(`${API_BASE}/api/admin/evaluation/summary`);
  const incomingParams = new URL(request.url).searchParams;
  incomingParams.forEach((value, key) => {
    upstreamUrl.searchParams.set(key, value);
  });

  const upstreamResponse = await fetch(upstreamUrl.toString(), {
    headers: {
      'X-Admin-Secret': adminSecret,
    },
    cache: 'no-store',
  });

  const contentType = upstreamResponse.headers.get('content-type') || 'application/json';
  const body = await upstreamResponse.text();

  return new NextResponse(body, {
    status: upstreamResponse.status,
    headers: {
      'Content-Type': contentType,
    },
  });
}
