import { NextResponse } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  const authorization = request.headers.get('authorization');
  if (!authorization) {
    return NextResponse.json({ detail: 'Authorization required' }, { status: 401 });
  }

  const upstreamUrl = new URL(`${API_BASE}/api/admin/evaluation/export/authenticated`);
  const incomingParams = new URL(request.url).searchParams;
  incomingParams.forEach((value, key) => {
    upstreamUrl.searchParams.set(key, value);
  });

  const upstreamResponse = await fetch(upstreamUrl.toString(), {
    headers: {
      Authorization: authorization,
    },
    cache: 'no-store',
  });

  const contentType = upstreamResponse.headers.get('content-type') || 'application/json';
  const contentDisposition = upstreamResponse.headers.get('content-disposition');
  const body = await upstreamResponse.text();

  const headers = {
    'Content-Type': contentType,
  };
  if (contentDisposition) {
    headers['Content-Disposition'] = contentDisposition;
  }

  return new NextResponse(body, {
    status: upstreamResponse.status,
    headers,
  });
}
