-- Migration: Dynamic Group Sizing
-- Description: Support optional group size limits and auto-maintained member counts.

ALTER TABLE roommate_groups
ADD COLUMN IF NOT EXISTS current_member_count INTEGER NOT NULL DEFAULT 1;

UPDATE roommate_groups rg
SET current_member_count = (
  SELECT COUNT(*)
  FROM group_members gm
  WHERE gm.group_id = rg.id
    AND gm.status = 'accepted'
);

ALTER TABLE roommate_groups
ALTER COLUMN target_group_size DROP NOT NULL;

CREATE OR REPLACE FUNCTION update_group_member_count()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' AND NEW.status = 'accepted' THEN
    UPDATE roommate_groups
    SET current_member_count = current_member_count + 1
    WHERE id = NEW.group_id;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' AND OLD.status = 'accepted' THEN
    UPDATE roommate_groups
    SET current_member_count = GREATEST(current_member_count - 1, 0)
    WHERE id = OLD.group_id;
    RETURN OLD;
  ELSIF TG_OP = 'UPDATE' THEN
    IF OLD.status = 'accepted' AND NEW.status != 'accepted' THEN
      UPDATE roommate_groups
      SET current_member_count = GREATEST(current_member_count - 1, 0)
      WHERE id = NEW.group_id;
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

DROP TRIGGER IF EXISTS group_member_count_trigger ON group_members;

CREATE TRIGGER group_member_count_trigger
AFTER INSERT OR UPDATE OR DELETE ON group_members
FOR EACH ROW EXECUTE FUNCTION update_group_member_count();

CREATE INDEX IF NOT EXISTS idx_roommate_groups_open_spots
ON roommate_groups(target_city, status, current_member_count, target_group_size)
WHERE status = 'active';
