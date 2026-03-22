-- Migration: Add preferred_neighborhoods to personal_preferences
-- Purpose: Align remote schema with app (preferences API, matching); fixes PGRST204
-- Date: 2026-03-21

BEGIN;

ALTER TABLE public.personal_preferences
ADD COLUMN IF NOT EXISTS preferred_neighborhoods text[];

UPDATE public.personal_preferences
SET preferred_neighborhoods = ARRAY[]::text[]
WHERE preferred_neighborhoods IS NULL;

CREATE INDEX IF NOT EXISTS idx_personal_preferences_preferred_neighborhoods
ON public.personal_preferences USING gin (preferred_neighborhoods);

COMMIT;
