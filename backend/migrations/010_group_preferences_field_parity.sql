-- Migration: Group preferences field parity with personal_preferences
-- Purpose: Persist the same preference field set on roommate_groups
-- Date: 2026-03-21

BEGIN;

ALTER TABLE public.roommate_groups
ADD COLUMN IF NOT EXISTS budget_min numeric,
ADD COLUMN IF NOT EXISTS budget_max numeric,
ADD COLUMN IF NOT EXISTS move_in_date date,
ADD COLUMN IF NOT EXISTS required_bedrooms integer,
ADD COLUMN IF NOT EXISTS preferred_neighborhoods text[],
ADD COLUMN IF NOT EXISTS lifestyle_preferences jsonb;

-- Backfill alias fields from legacy group columns.
UPDATE public.roommate_groups
SET
    budget_min = COALESCE(budget_min, budget_per_person_min),
    budget_max = COALESCE(budget_max, budget_per_person_max),
    move_in_date = COALESCE(move_in_date, target_move_in_date),
    required_bedrooms = COALESCE(required_bedrooms, target_bedrooms)
WHERE
    budget_min IS NULL
    OR budget_max IS NULL
    OR move_in_date IS NULL
    OR required_bedrooms IS NULL;

-- Keep list/object fields in a canonical non-null shape.
UPDATE public.roommate_groups
SET preferred_neighborhoods = ARRAY[]::text[]
WHERE preferred_neighborhoods IS NULL;

UPDATE public.roommate_groups
SET lifestyle_preferences = '{}'::jsonb
WHERE lifestyle_preferences IS NULL;

CREATE INDEX IF NOT EXISTS idx_roommate_groups_budget_min
ON public.roommate_groups(budget_min);

CREATE INDEX IF NOT EXISTS idx_roommate_groups_move_in_date
ON public.roommate_groups(move_in_date);

COMMIT;
