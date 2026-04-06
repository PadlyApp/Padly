-- Migration: Fix swipe_interactions RLS policies
-- Purpose: The original INSERT/SELECT policies compared actor_user_id to auth.uid(),
--          but actor_user_id stores users.id (internal UUID) while auth.uid() returns
--          the auth UUID stored as users.auth_id. These are different UUIDs, causing
--          every INSERT/SELECT via a user JWT to fail the policy check.
--          This migration replaces the policies with a sub-select join on users.auth_id.
-- Date: 2026-04-06

BEGIN;

DROP POLICY IF EXISTS "swipe_interactions_insert_own" ON public.swipe_interactions;
CREATE POLICY "swipe_interactions_insert_own"
ON public.swipe_interactions
FOR INSERT
TO authenticated
WITH CHECK (
  actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

DROP POLICY IF EXISTS "swipe_interactions_select_own" ON public.swipe_interactions;
CREATE POLICY "swipe_interactions_select_own"
ON public.swipe_interactions
FOR SELECT
TO authenticated
USING (
  actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

-- Add a matching DELETE policy so users can clean up their own records
-- (used by the unsave endpoint when the service role is not available).
DROP POLICY IF EXISTS "swipe_interactions_delete_own" ON public.swipe_interactions;
CREATE POLICY "swipe_interactions_delete_own"
ON public.swipe_interactions
FOR DELETE
TO authenticated
USING (
  actor_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
);

COMMIT;
