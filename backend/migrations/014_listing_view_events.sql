-- Migration: Create listing_view_events table
-- Purpose: Track how long users look at listings before acting.
--          Key signal for AI training and realtor engagement analytics.
-- Surfaces: discover_card (swipe stack), listing_detail (full page), matches_card (matches grid)
-- Date: 2026-04-03

BEGIN;

CREATE TABLE IF NOT EXISTS public.listing_view_events (
    event_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    listing_id          uuid        NOT NULL REFERENCES public.listings(id) ON DELETE CASCADE,
    surface             text        NOT NULL CHECK (surface IN ('discover_card', 'listing_detail', 'matches_card')),
    session_id          text        NOT NULL,
    view_duration_ms    integer     NULL CHECK (view_duration_ms IS NULL OR view_duration_ms >= 0),
    expanded            boolean     NOT NULL DEFAULT false,
    photos_viewed_count integer     NOT NULL DEFAULT 0 CHECK (photos_viewed_count >= 0),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_listing_view_events_user_created_at
    ON public.listing_view_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_listing_view_events_listing_created_at
    ON public.listing_view_events (listing_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_listing_view_events_surface
    ON public.listing_view_events (surface, created_at DESC);

COMMENT ON TABLE public.listing_view_events IS
    'Records how long a user views a listing card or detail page before acting.';

COMMENT ON COLUMN public.listing_view_events.surface IS
    'Where the view occurred: discover_card (swipe stack), listing_detail (full page), matches_card (matches grid).';

COMMENT ON COLUMN public.listing_view_events.expanded IS
    'True if the user tapped to open the detail modal or navigated to the full listing page during this view.';

COMMENT ON COLUMN public.listing_view_events.photos_viewed_count IS
    'Number of distinct photo advances observed during the view (auto-advance + manual swipe).';

COMMENT ON COLUMN public.listing_view_events.view_duration_ms IS
    'Null if the user navigated away without triggering a clean unmount (tab close, crash).';

COMMIT;
