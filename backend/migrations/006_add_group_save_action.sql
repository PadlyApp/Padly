-- Migration: Add 'group_save' to swipe_interactions action constraint
-- Purpose: Allow users to star/bookmark listings to their group from the Matches page
-- Date: 2026-04-01

BEGIN;

ALTER TABLE public.swipe_interactions
  DROP CONSTRAINT IF EXISTS swipe_interactions_action_check;

ALTER TABLE public.swipe_interactions
  ADD CONSTRAINT swipe_interactions_action_check
  CHECK (action IN ('like', 'pass', 'super_like', 'group_save'));

COMMIT;
