-- Rollback Migration: Dynamic Group Sizing
-- Date: 2025-11-30
-- Description: Revert changes from 001_dynamic_group_sizing.sql

-- ============================================================================
-- Step 1: Drop trigger
-- ============================================================================

DROP TRIGGER IF EXISTS group_member_count_trigger ON group_members;

-- ============================================================================
-- Step 2: Drop function
-- ============================================================================

DROP FUNCTION IF EXISTS update_group_member_count();

-- ============================================================================
-- Step 3: Drop index
-- ============================================================================

DROP INDEX IF EXISTS idx_roommate_groups_open_spots;

-- ============================================================================
-- Step 4: Make target_group_size NOT NULL again (restore original)
-- ============================================================================

-- Set default value for any nulls before making NOT NULL
UPDATE roommate_groups 
SET target_group_size = 2 
WHERE target_group_size IS NULL;

ALTER TABLE roommate_groups 
ALTER COLUMN target_group_size SET NOT NULL;

-- ============================================================================
-- Step 5: Remove current_member_count column
-- ============================================================================

ALTER TABLE roommate_groups 
DROP COLUMN IF EXISTS current_member_count;
