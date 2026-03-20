-- Migration: Add swipe_interactions table for Discover feedback capture
-- Purpose: Phase 1 event storage for user swipe behavior
-- Date: 2026-03-20

BEGIN;

CREATE TABLE IF NOT EXISTS public.swipe_interactions (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_type text NOT NULL DEFAULT 'user' CHECK (actor_type IN ('user')),
    actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    group_id_at_time uuid NULL REFERENCES public.roommate_groups(id) ON DELETE SET NULL,
    listing_id uuid NOT NULL REFERENCES public.listings(id) ON DELETE CASCADE,
    action text NOT NULL CHECK (action IN ('like', 'pass', 'super_like')),
    surface text NOT NULL DEFAULT 'discover',
    session_id text NOT NULL,
    position_in_feed integer NOT NULL DEFAULT 0,
    algorithm_version text NULL,
    model_version text NULL,
    city_filter text NULL,
    preference_snapshot_hash text NULL,
    latency_ms integer NULL CHECK (latency_ms IS NULL OR latency_ms >= 0),
    created_at timestamp with time zone NOT NULL DEFAULT now()
);

-- Idempotency guard for repeated client submissions.
CREATE UNIQUE INDEX IF NOT EXISTS idx_swipe_interactions_idempotency
ON public.swipe_interactions(actor_user_id, listing_id, session_id, position_in_feed);

CREATE INDEX IF NOT EXISTS idx_swipe_interactions_user_created_at
ON public.swipe_interactions(actor_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_swipe_interactions_group_created_at
ON public.swipe_interactions(group_id_at_time, created_at DESC)
WHERE group_id_at_time IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_swipe_interactions_listing_created_at
ON public.swipe_interactions(listing_id, created_at DESC);

COMMENT ON TABLE public.swipe_interactions IS 'Discover swipe events used for behavior features and ranking experiments.';
COMMENT ON COLUMN public.swipe_interactions.position_in_feed IS '0-based position when the listing was shown.';
COMMENT ON COLUMN public.swipe_interactions.preference_snapshot_hash IS 'Optional hash of the active preference snapshot used by client.';

COMMIT;

