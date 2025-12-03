-- Migration: Add confirmation tracking to stable_matches
-- Purpose: Enable Option 3 (Hybrid Re-matching) by tracking which matches have been confirmed
-- A match is fully confirmed when BOTH group_confirmed_at AND listing_confirmed_at are NOT NULL

-- Add confirmation timestamp columns
ALTER TABLE stable_matches
ADD COLUMN IF NOT EXISTS group_confirmed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
ADD COLUMN IF NOT EXISTS listing_confirmed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- Add index for efficient querying of unconfirmed matches
CREATE INDEX IF NOT EXISTS idx_stable_matches_unconfirmed 
ON stable_matches (group_id, listing_id) 
WHERE group_confirmed_at IS NULL OR listing_confirmed_at IS NULL;

-- Add index for confirmed matches
CREATE INDEX IF NOT EXISTS idx_stable_matches_confirmed 
ON stable_matches (group_id, listing_id) 
WHERE group_confirmed_at IS NOT NULL AND listing_confirmed_at IS NOT NULL;

-- Update status enum to include more states (optional, for additional clarity)
-- Note: Existing 'active' status remains valid
-- Possible future states: 'active', 'expired', 'cancelled', 'superseded'

-- Comment on new columns for documentation
COMMENT ON COLUMN stable_matches.group_confirmed_at IS 'Timestamp when the group confirmed this match. NULL means pending group confirmation.';
COMMENT ON COLUMN stable_matches.listing_confirmed_at IS 'Timestamp when the listing owner confirmed this match. NULL means pending listing confirmation.';

-- Rollback commands (run manually if needed):
-- ALTER TABLE stable_matches DROP COLUMN IF EXISTS group_confirmed_at;
-- ALTER TABLE stable_matches DROP COLUMN IF EXISTS listing_confirmed_at;
-- DROP INDEX IF EXISTS idx_stable_matches_unconfirmed;
-- DROP INDEX IF EXISTS idx_stable_matches_confirmed;
