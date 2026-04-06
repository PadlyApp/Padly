-- Migration: RLS policies for search_query_events
-- Date: 2026-04-03

BEGIN;

GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.search_query_events TO authenticated, service_role;

ALTER TABLE public.search_query_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "search_query_events_insert_own" ON public.search_query_events;
CREATE POLICY "search_query_events_insert_own"
    ON public.search_query_events
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "search_query_events_select_own" ON public.search_query_events;
CREATE POLICY "search_query_events_select_own"
    ON public.search_query_events
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

COMMIT;
