-- Migration: RLS policies for page_view_events
-- Date: 2026-04-03

BEGIN;

GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.page_view_events TO authenticated, service_role;

ALTER TABLE public.page_view_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "page_view_events_insert_own" ON public.page_view_events;
CREATE POLICY "page_view_events_insert_own"
    ON public.page_view_events
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid() OR user_id IS NULL);

DROP POLICY IF EXISTS "page_view_events_select_own" ON public.page_view_events;
CREATE POLICY "page_view_events_select_own"
    ON public.page_view_events
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

COMMIT;
