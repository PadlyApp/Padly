-- Migration: Dynamic Group Sizing
-- Date: 2025-11-30
-- Description: Update roommate_groups to support flexible group sizes and automatic member counting

-- ============================================================================
-- Step 1: Add current_member_count column
-- ============================================================================

ALTER TABLE roommate_groups 
ADD COLUMN IF NOT EXISTS current_member_count INTEGER NOT NULL DEFAULT 1;

-- Initialize current_member_count for existing groups based on actual members
UPDATE roommate_groups rg
SET current_member_count = (
  SELECT COUNT(*)
  FROM group_members gm
  WHERE gm.group_id = rg.id 
    AND gm.status = 'accepted'
);

-- ============================================================================
-- Step 2: Make target_group_size nullable (optional)
-- ============================================================================

ALTER TABLE roommate_groups 
ALTER COLUMN target_group_size DROP NOT NULL;

-- ============================================================================
-- Step 3: Create function to auto-update current_member_count
-- ============================================================================

CREATE OR REPLACE FUNCTION update_group_member_count()
RETURNS TRIGGER AS $$
BEGIN
  -- When a member is added (INSERT with accepted status)
  IF TG_OP = 'INSERT' AND NEW.status = 'accepted' THEN
    UPDATE roommate_groups 
    SET current_member_count = current_member_count + 1
    WHERE id = NEW.group_id;
    RETURN NEW;
  
  -- When a member is removed (DELETE with accepted status)
  ELSIF TG_OP = 'DELETE' AND OLD.status = 'accepted' THEN
    UPDATE roommate_groups 
    SET current_member_count = GREATEST(current_member_count - 1, 0)
    WHERE id = OLD.group_id;
    RETURN OLD;
  
  -- When member status changes
  ELSIF TG_OP = 'UPDATE' THEN
    -- From accepted to something else (member leaving)
    IF OLD.status = 'accepted' AND NEW.status != 'accepted' THEN
      UPDATE roommate_groups 
      SET current_member_count = GREATEST(current_member_count - 1, 0)
      WHERE id = NEW.group_id;
    
    -- From something else to accepted (member joining)
    ELSIF OLD.status != 'accepted' AND NEW.status = 'accepted' THEN
      UPDATE roommate_groups 
      SET current_member_count = current_member_count + 1
      WHERE id = NEW.group_id;
    END IF;
    RETURN NEW;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Step 4: Create trigger on group_members table
-- ============================================================================

DROP TRIGGER IF EXISTS group_member_count_trigger ON group_members;

CREATE TRIGGER group_member_count_trigger
AFTER INSERT OR UPDATE OR DELETE ON group_members
FOR EACH ROW EXECUTE FUNCTION update_group_member_count();

-- ============================================================================
-- Step 5: Add index for better query performance
-- ============================================================================

-- Index for finding open groups (where current < target or target is null)
CREATE INDEX IF NOT EXISTS idx_roommate_groups_open_spots 
ON roommate_groups(target_city, status, current_member_count, target_group_size)
WHERE status = 'active';

-- ============================================================================
-- Verification Queries (run these to test)
-- ============================================================================

-- Check that current_member_count matches actual members
-- SELECT 
--   rg.id,
--   rg.group_name,
--   rg.current_member_count as counted,
--   (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = rg.id AND gm.status = 'accepted') as actual
-- FROM roommate_groups rg;

-- Find all open groups (accepting new members)
-- SELECT id, group_name, current_member_count, target_group_size
-- FROM roommate_groups
-- WHERE status = 'active'
--   AND (target_group_size IS NULL OR current_member_count < target_group_size);
