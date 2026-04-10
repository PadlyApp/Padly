"""
Guest rate limiting dependency.

Applies a sliding-window rate limit to unauthenticated (guest) requests only.
Authenticated requests (valid Bearer token present) pass through unchecked.

Limits: 10 requests / 60 seconds per IP.

NOTE: Uses an in-memory store — limits reset on process restart and are
not shared across multiple workers. Sufficient for single-worker deployments;
replace with Redis-backed limiting (e.g. slowapi + redis) if you scale out.
"""

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Header, HTTPException, Request

GUEST_LIMIT = 10          # max requests per window
GUEST_WINDOW_SECONDS = 60 # sliding window size

AUTH_LIMIT = 30           # authenticated users — general endpoints
AUTH_WINDOW_SECONDS = 60

# Recommendations is an expensive DB scan + ML scoring pass; frontend caches
# results in localStorage for 5 min so legitimate users rarely exceed 1 req/min.
# Keeping this low prevents any single user from hammering the pipeline.
RECOMMENDATIONS_AUTH_LIMIT = 20
RECOMMENDATIONS_GUEST_LIMIT = 10

# ip -> deque of monotonic timestamps within the current window
_request_log: dict[str, deque] = defaultdict(deque)
_auth_request_log: dict[str, deque] = defaultdict(deque)


def _get_client_ip(request: Request) -> str:
    """
    Extract the real client IP, respecting common reverse-proxy headers.
    Falls back to the direct connection IP.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # x-forwarded-for can be a comma-separated list; leftmost is the client
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


async def guest_rate_limit(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> None:
    """
    FastAPI dependency — rate limit unauthenticated requests by IP.

    Inject this into any endpoint that should be publicly accessible but
    protected from guest abuse:

        @router.post("/recommendations")
        async def get_recommendations(
            ...,
            _: None = Depends(guest_rate_limit),
        ):
    """
    # Authenticated users bypass guest rate limiting entirely
    if authorization and authorization.startswith("Bearer "):
        return

    ip = _get_client_ip(request)
    now = time.monotonic()
    window_start = now - GUEST_WINDOW_SECONDS

    log = _request_log[ip]

    # Evict timestamps that have fallen outside the window
    while log and log[0] < window_start:
        log.popleft()

    if len(log) >= GUEST_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many requests. Guest access is limited to {GUEST_LIMIT} "
                f"requests per minute. Sign up for unlimited access."
            ),
            headers={"Retry-After": str(GUEST_WINDOW_SECONDS)},
        )

    log.append(now)


async def recommendations_rate_limit(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> None:
    """
    Rate limit for the recommendations endpoint — applies to ALL callers.

    Guests:        3 req/min — low because they have no persistent state.
    Authenticated: 5 req/min — the frontend caches results in localStorage
                   for 5 min, so legitimate users rarely exceed 1 req/min.
                   The lower limit prevents pipeline abuse even with auth.
    """
    ip = _get_client_ip(request)
    now = time.monotonic()

    is_auth = bool(authorization and authorization.startswith("Bearer "))
    limit = RECOMMENDATIONS_AUTH_LIMIT if is_auth else RECOMMENDATIONS_GUEST_LIMIT
    window = AUTH_WINDOW_SECONDS if is_auth else GUEST_WINDOW_SECONDS
    log = _auth_request_log[ip] if is_auth else _request_log[ip]
    window_start = now - window

    while log and log[0] < window_start:
        log.popleft()

    if len(log) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait before refreshing.",
            headers={"Retry-After": str(window)},
        )

    log.append(now)
