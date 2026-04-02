-- Migration: Remove office location fields from users
-- Purpose: Simplify onboarding and preferences flow by removing office location
-- Date: 2026-03-20

BEGIN;

ALTER TABLE public.users
DROP CONSTRAINT IF EXISTS users_office_location_completeness_check;

ALTER TABLE public.users
DROP CONSTRAINT IF EXISTS users_office_country_check;

DROP INDEX IF EXISTS public.idx_users_office_city;
DROP INDEX IF EXISTS public.idx_users_office_location;

ALTER TABLE public.users
DROP COLUMN IF EXISTS office_country,
DROP COLUMN IF EXISTS office_state_province,
DROP COLUMN IF EXISTS office_city;

COMMIT;
