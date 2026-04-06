-- Migration: Recommendation passive metrics storage
-- Purpose: Phase 3 storage for position-aware engagement events and dwell metrics
-- Date: 2026-04-06

BEGIN;

ALTER TABLE public.recommendation_sessions
ADD COLUMN IF NOT EXISTS surface_dwell_ms bigint NOT NULL DEFAULT 0 CHECK (surface_dwell_ms >= 0);

ALTER TABLE public.recommendation_sessions
ADD COLUMN IF NOT EXISTS detail_dwell_ms bigint NOT NULL DEFAULT 0 CHECK (detail_dwell_ms >= 0);

CREATE TABLE IF NOT EXISTS public.recommendation_engagement_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    recommendation_session_id uuid NOT NULL REFERENCES public.recommendation_sessions(id) ON DELETE CASCADE,
    client_event_id text NOT NULL,
    surface text NOT NULL CHECK (surface IN ('matches', 'discover')),
    event_type text NOT NULL CHECK (event_type IN ('detail_open', 'detail_view', 'save', 'unsave')),
    listing_id uuid NULL REFERENCES public.listings(id) ON DELETE CASCADE,
    position_in_feed integer NULL CHECK (position_in_feed IS NULL OR position_in_feed >= 0),
    dwell_ms bigint NULL CHECK (dwell_ms IS NULL OR dwell_ms >= 0),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT recommendation_engagement_events_actor_client_unique UNIQUE (actor_user_id, client_event_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendation_engagement_events_session_created_at
ON public.recommendation_engagement_events(recommendation_session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendation_engagement_events_type_created_at
ON public.recommendation_engagement_events(event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendation_engagement_events_listing_created_at
ON public.recommendation_engagement_events(listing_id, created_at DESC)
WHERE listing_id IS NOT NULL;

COMMENT ON TABLE public.recommendation_engagement_events IS 'Passive engagement events tied to a recommendation session with listing rank context.';
COMMENT ON COLUMN public.recommendation_engagement_events.client_event_id IS 'Client-generated idempotency key for a passive engagement event.';
COMMENT ON COLUMN public.recommendation_sessions.surface_dwell_ms IS 'Total time spent on the recommendation surface for the session.';
COMMENT ON COLUMN public.recommendation_sessions.detail_dwell_ms IS 'Total time spent on listing detail pages entered from the recommendation session.';

GRANT SELECT, INSERT ON TABLE public.recommendation_engagement_events TO authenticated, service_role;

ALTER TABLE public.recommendation_engagement_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "recommendation_engagement_events_insert_own" ON public.recommendation_engagement_events;
CREATE POLICY "recommendation_engagement_events_insert_own"
ON public.recommendation_engagement_events
FOR INSERT
TO authenticated
WITH CHECK (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

DROP POLICY IF EXISTS "recommendation_engagement_events_select_own" ON public.recommendation_engagement_events;
CREATE POLICY "recommendation_engagement_events_select_own"
ON public.recommendation_engagement_events
FOR SELECT
TO authenticated
USING (
    actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

COMMIT;
