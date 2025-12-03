-- ============================================================================
-- DATABASE MIGRATION: Expand personal_preferences table
-- ============================================================================
-- This migration adds 9 columns needed for housing preference matching
-- Status: Ready to execute in Supabase SQL Editor
-- Time: ~5 seconds to execute
-- ============================================================================

-- Copy and paste this entire block into Supabase SQL Editor and click "Run"

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

-- ============================================================================
-- Verification Queries (Run after migration succeeds)
-- ============================================================================

-- 1. Verify all columns were created
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'personal_preferences' 
  AND column_name IN (
    'target_state_province', 'required_bedrooms', 'target_lease_type',
    'target_lease_duration_months', 'target_bathrooms', 'target_furnished',
    'target_utilities_included', 'target_deposit_amount', 'target_house_rules'
  )
ORDER BY column_name;
-- Expected: 9 rows

-- 2. Verify indexes were created
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'personal_preferences' 
  AND (indexname LIKE '%target_city%' OR indexname LIKE '%move_in_date%');
-- Expected: 2 rows

-- 3. Check table structure (run this in psql, not Supabase)
-- \d public.personal_preferences
-- Should show all 13 expected columns for preferences

-- ============================================================================
-- If Migration Fails
-- ============================================================================

-- If you get an error "column already exists", that's OK - it means the
-- migration was already applied. The "IF NOT EXISTS" prevents duplicates.

-- If you get other errors:
-- 1. Check that you're connected to the correct Supabase project
-- 2. Verify the user executing has admin/superuser privileges
-- 3. Check Supabase logs for detailed error messages
-- 4. Reach out to team with error message

-- ============================================================================
