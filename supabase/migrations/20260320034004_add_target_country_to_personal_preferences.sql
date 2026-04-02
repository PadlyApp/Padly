-- Migration: Add target_country to personal_preferences
-- Purpose: Support strict country/state/city controlled vocabulary
-- Date: 2026-03-20

BEGIN;

ALTER TABLE public.personal_preferences
ADD COLUMN IF NOT EXISTS target_country text;

-- Backfill missing country using default US (can be edited to CA in UI).
UPDATE public.personal_preferences
SET target_country = 'US'
WHERE target_country IS NULL;

-- Optional soft guard: keep values within supported countries when set.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'personal_preferences'
          AND constraint_name = 'personal_preferences_target_country_check'
    ) THEN
        ALTER TABLE public.personal_preferences
        ADD CONSTRAINT personal_preferences_target_country_check
        CHECK (target_country IS NULL OR target_country IN ('US', 'CA'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_personal_preferences_target_country
ON public.personal_preferences(target_country);

COMMIT;

