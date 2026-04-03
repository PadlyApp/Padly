-- Migration: RLS policies for listing_view_events
-- Date: 2026-04-03

BEGIN;

GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.listing_view_events TO authenticated, service_role;

ALTER TABLE public.listing_view_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "listing_view_events_insert_own" ON public.listing_view_events;
CREATE POLICY "listing_view_events_insert_own"
    ON public.listing_view_events
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "listing_view_events_select_own" ON public.listing_view_events;
CREATE POLICY "listing_view_events_select_own"
    ON public.listing_view_events
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

COMMIT;
