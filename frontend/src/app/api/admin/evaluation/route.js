import { NextResponse } from 'next/server';
import { apiUrl } from '../../../../../lib/api';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  const authorization = request.headers.get('authorization');
  if (!authorization) {
    return NextResponse.json({ detail: 'Authorization required' }, { status: 401 });
  }

  const upstreamUrl = new URL(apiUrl('/admin/evaluation/summary/authenticated'));
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
  const body = await upstreamResponse.text();

  return new NextResponse(body, {
    status: upstreamResponse.status,
    headers: {
      'Content-Type': contentType,
    },
  });
}
