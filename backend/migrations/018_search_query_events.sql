-- Migration: Create search_query_events table
-- Purpose: Demand intelligence — capture what users search/filter for when loading
--          the discover feed. Sellable to realtors as aggregated market demand data.
-- Date: 2026-04-03

BEGIN;

CREATE TABLE IF NOT EXISTS public.search_query_events (
    event_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    session_id       text        NOT NULL,
    filter_snapshot  jsonb       NOT NULL,
    results_returned integer     NOT NULL DEFAULT 0 CHECK (results_returned >= 0),
    "offset"         integer     NOT NULL DEFAULT 0 CHECK ("offset" >= 0),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_search_query_events_user_created_at
    ON public.search_query_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_query_events_created_at
    ON public.search_query_events (created_at DESC);

-- GIN index enables queries like: WHERE filter_snapshot @> '{"target_city": "Toronto"}'
CREATE INDEX IF NOT EXISTS idx_search_query_events_filter_snapshot
    ON public.search_query_events USING gin (filter_snapshot);

COMMENT ON TABLE public.search_query_events IS
    'Captures each discover feed load with the active filter state and result count. Pure demand intelligence.';

COMMENT ON COLUMN public.search_query_events.filter_snapshot IS
    'Full copy of the preference/filter object sent to /api/recommendations.';

COMMENT ON COLUMN public.search_query_events."offset" IS
    'Pagination offset; 0 means a fresh search, >0 means load-more triggered.';

COMMIT;
