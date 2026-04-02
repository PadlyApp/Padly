-- Migration: Preferences hard/soft restructure support
-- Purpose: Add explicit fields for furnished preference and gender policy
-- Date: 2026-03-20

BEGIN;

ALTER TABLE public.personal_preferences
ADD COLUMN IF NOT EXISTS furnished_preference text,
ADD COLUMN IF NOT EXISTS gender_policy text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'personal_preferences'
          AND constraint_name = 'personal_preferences_furnished_preference_check'
    ) THEN
        ALTER TABLE public.personal_preferences
        ADD CONSTRAINT personal_preferences_furnished_preference_check
        CHECK (
            furnished_preference IS NULL
            OR furnished_preference IN ('required', 'preferred', 'no_preference')
        );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'personal_preferences'
          AND constraint_name = 'personal_preferences_gender_policy_check'
    ) THEN
        ALTER TABLE public.personal_preferences
        ADD CONSTRAINT personal_preferences_gender_policy_check
        CHECK (
            gender_policy IS NULL
            OR gender_policy IN ('same_gender_only', 'mixed_ok')
        );
    END IF;
END $$;

ALTER TABLE public.roommate_groups
ADD COLUMN IF NOT EXISTS furnished_preference text,
ADD COLUMN IF NOT EXISTS gender_policy text,
ADD COLUMN IF NOT EXISTS furnished_is_hard boolean NOT NULL DEFAULT false;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'roommate_groups'
          AND constraint_name = 'roommate_groups_furnished_preference_check'
    ) THEN
        ALTER TABLE public.roommate_groups
        ADD CONSTRAINT roommate_groups_furnished_preference_check
        CHECK (
            furnished_preference IS NULL
            OR furnished_preference IN ('required', 'preferred', 'no_preference')
        );
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'roommate_groups'
          AND constraint_name = 'roommate_groups_gender_policy_check'
    ) THEN
        ALTER TABLE public.roommate_groups
        ADD CONSTRAINT roommate_groups_gender_policy_check
        CHECK (
            gender_policy IS NULL
            OR gender_policy IN ('same_gender_only', 'mixed_ok')
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_personal_preferences_furnished_preference
ON public.personal_preferences(furnished_preference);

CREATE INDEX IF NOT EXISTS idx_personal_preferences_gender_policy
ON public.personal_preferences(gender_policy);

COMMIT;
