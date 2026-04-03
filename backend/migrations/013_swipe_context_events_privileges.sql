-- Migration: RLS policies for swipe_context_events
-- Date: 2026-04-03

BEGIN;

GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT ON TABLE public.swipe_context_events TO authenticated, service_role;

ALTER TABLE public.swipe_context_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "swipe_context_events_insert_own" ON public.swipe_context_events;
CREATE POLICY "swipe_context_events_insert_own"
    ON public.swipe_context_events
    FOR INSERT
    TO authenticated
    WITH CHECK (actor_user_id = auth.uid());

DROP POLICY IF EXISTS "swipe_context_events_select_own" ON public.swipe_context_events;
CREATE POLICY "swipe_context_events_select_own"
    ON public.swipe_context_events
    FOR SELECT
    TO authenticated
    USING (actor_user_id = auth.uid());

COMMIT;
