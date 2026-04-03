-- Migration: Create page_view_events table
-- Purpose: Funnel analytics — track which pages users visit and for how long.
--          Reveals drop-off points in the signup → preferences → discover → match funnel.
-- Date: 2026-04-03

BEGIN;

CREATE TABLE IF NOT EXISTS public.page_view_events (
    event_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid        NULL REFERENCES public.users(id) ON DELETE SET NULL,
    page          text        NOT NULL CHECK (page IN (
                                  'discover', 'matches', 'listing_detail', 'preferences',
                                  'account', 'groups', 'roommates', 'onboarding'
                              )),
    session_id    text        NOT NULL,
    duration_ms   integer     NULL CHECK (duration_ms IS NULL OR duration_ms >= 0),
    referrer_page text        NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Partial index: only index authenticated views
CREATE INDEX IF NOT EXISTS idx_page_view_events_user_created_at
    ON public.page_view_events (user_id, created_at DESC)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_page_view_events_page_created_at
    ON public.page_view_events (page, created_at DESC);

COMMENT ON TABLE public.page_view_events IS
    'Page-level funnel analytics. Nullable user_id supports future anonymous tracking.';

COMMENT ON COLUMN public.page_view_events.duration_ms IS
    'Null if the user navigated away without triggering a clean React unmount (e.g. tab close).';

COMMENT ON COLUMN public.page_view_events.referrer_page IS
    'The page the user came from within the app, if known.';

COMMIT;
