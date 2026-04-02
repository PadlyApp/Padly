-- Migration: Grant privileges and RLS policies for swipe_interactions
-- Purpose: Ensure authenticated users and service role can access table safely
-- Date: 2026-03-20

BEGIN;

-- Ensure schema/table access for API roles.
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.swipe_interactions TO authenticated, service_role;

-- Enforce user-scoped access for authenticated tokens.
ALTER TABLE public.swipe_interactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "swipe_interactions_insert_own" ON public.swipe_interactions;
CREATE POLICY "swipe_interactions_insert_own"
ON public.swipe_interactions
FOR INSERT
TO authenticated
WITH CHECK (actor_user_id = auth.uid());

DROP POLICY IF EXISTS "swipe_interactions_select_own" ON public.swipe_interactions;
CREATE POLICY "swipe_interactions_select_own"
ON public.swipe_interactions
FOR SELECT
TO authenticated
USING (actor_user_id = auth.uid());

COMMIT;

