-- Migration: Add office location fields to users
-- Purpose: Capture office location at registration for commute-aware matching
-- Date: 2026-03-20

BEGIN;

ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS office_country text,
ADD COLUMN IF NOT EXISTS office_state_province text,
ADD COLUMN IF NOT EXISTS office_city text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND constraint_name = 'users_office_country_check'
    ) THEN
        ALTER TABLE public.users
        ADD CONSTRAINT users_office_country_check
        CHECK (office_country IS NULL OR office_country IN ('US', 'CA'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND constraint_name = 'users_office_location_completeness_check'
    ) THEN
        ALTER TABLE public.users
        ADD CONSTRAINT users_office_location_completeness_check
        CHECK (
            (office_country IS NULL AND office_state_province IS NULL AND office_city IS NULL)
            OR
            (office_country IS NOT NULL AND office_state_province IS NOT NULL AND office_city IS NOT NULL)
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_office_city
ON public.users(office_city);

CREATE INDEX IF NOT EXISTS idx_users_office_location
ON public.users(office_country, office_state_province, office_city);

COMMIT;

