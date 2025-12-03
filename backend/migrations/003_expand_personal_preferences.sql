-- Migration: Expand personal_preferences table with housing preference fields
-- Purpose: Add missing fields needed for the matching algorithm
-- Date: 2025-12-03

BEGIN;

-- Add missing hard constraint fields
ALTER TABLE public.personal_preferences
ADD COLUMN IF NOT EXISTS target_state_province text,
ADD COLUMN IF NOT EXISTS required_bedrooms integer,
ADD COLUMN IF NOT EXISTS target_lease_type text,
ADD COLUMN IF NOT EXISTS target_lease_duration_months integer;

-- Add missing soft preference fields
ALTER TABLE public.personal_preferences
ADD COLUMN IF NOT EXISTS target_bathrooms numeric,
ADD COLUMN IF NOT EXISTS target_furnished boolean,
ADD COLUMN IF NOT EXISTS target_utilities_included boolean,
ADD COLUMN IF NOT EXISTS target_deposit_amount numeric,
ADD COLUMN IF NOT EXISTS target_house_rules text;

-- Add index on target_city for faster queries
CREATE INDEX IF NOT EXISTS idx_personal_preferences_target_city 
ON public.personal_preferences(target_city);

-- Add index on move_in_date for range queries
CREATE INDEX IF NOT EXISTS idx_personal_preferences_move_in_date 
ON public.personal_preferences(move_in_date);

COMMIT;
