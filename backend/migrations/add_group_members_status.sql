-- Migration: Add status column to group_members table
-- This enables invitation tracking (pending, accepted, rejected)

-- Add status column with default 'accepted' for existing members
ALTER TABLE group_members 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'accepted' NOT NULL;

-- Add check constraint for valid statuses
ALTER TABLE group_members 
ADD CONSTRAINT IF NOT EXISTS check_status_values 
CHECK (status IN ('pending', 'accepted', 'rejected'));

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_group_members_status 
ON group_members(status);

CREATE INDEX IF NOT EXISTS idx_group_members_user_status 
ON group_members(user_id, status);

-- Add a comment explaining the column
COMMENT ON COLUMN group_members.status IS 'Invitation status: pending (invited but not accepted), accepted (active member), rejected (invitation declined)';
