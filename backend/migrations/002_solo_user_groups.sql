-- Migration: Solo User Groups Support
-- Date: 2025-12-01
-- Description: Add support for solo users by auto-creating 1-person groups

-- ============================================================================
-- Step 1: Add is_solo flag to roommate_groups
-- ============================================================================

ALTER TABLE roommate_groups 
ADD COLUMN IF NOT EXISTS is_solo BOOLEAN DEFAULT FALSE NOT NULL;

-- Add comment
COMMENT ON COLUMN roommate_groups.is_solo IS 
'Flag indicating if this is a solo user group (1 person) vs a real multi-person group. Solo groups are auto-created on signup.';

-- ============================================================================
-- Step 2: Add index for querying solo vs group users
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_roommate_groups_solo 
ON roommate_groups(is_solo, status);

-- ============================================================================
-- Step 3: Update existing solo groups (groups with only 1 member)
-- ============================================================================

-- Mark existing 1-person groups as solo
UPDATE roommate_groups rg
SET is_solo = TRUE
WHERE current_member_count = 1
  AND target_group_size = 1;

-- ============================================================================
-- Verification Query
-- ============================================================================

-- Check solo groups
-- SELECT id, group_name, is_solo, current_member_count, target_group_size
-- FROM roommate_groups
-- WHERE is_solo = TRUE;
