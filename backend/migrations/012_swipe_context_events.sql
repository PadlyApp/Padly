-- Migration: Create swipe_context_events table
-- Purpose: Companion to swipe_interactions. Captures filter state + device context
--          at swipe time without altering the existing prod table.
--          Join to swipe_interactions on (actor_user_id, listing_id, session_id).
-- Date: 2026-04-03

BEGIN;

CREATE TABLE IF NOT EXISTS public.swipe_context_events (
    event_id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id           uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    listing_id              uuid        NOT NULL REFERENCES public.listings(id) ON DELETE CASCADE,
    session_id              text        NOT NULL,
    action                  text        NOT NULL CHECK (action IN ('like', 'pass', 'super_like', 'group_save')),
    active_filters_snapshot jsonb       NULL,
    device_context          jsonb       NULL,
    created_at              timestamptz NOT NULL DEFAULT now()
);

-- Index to join back to swipe_interactions
CREATE INDEX IF NOT EXISTS idx_swipe_context_events_user_session
    ON public.swipe_context_events (actor_user_id, session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_swipe_context_events_listing
    ON public.swipe_context_events (listing_id, created_at DESC);

COMMENT ON TABLE public.swipe_context_events IS
    'Companion to swipe_interactions. Stores filter + device context at swipe time. Join on (actor_user_id, listing_id, session_id).';

COMMENT ON COLUMN public.swipe_context_events.active_filters_snapshot IS
    'Full copy of the preference/filter object active at the time of the swipe (budget, city, bedrooms, etc.).';

COMMENT ON COLUMN public.swipe_context_events.device_context IS
    'Browser-collected device context: device_type, os, browser, screen_width, screen_height, connection_type.';

COMMIT;
