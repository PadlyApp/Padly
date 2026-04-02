-- Migration: Fix mutable search_path on public functions
-- Date: 2026-04-02
--
-- Functions without a fixed search_path can be exploited via search_path
-- injection if a malicious schema is placed earlier in the search path.
-- Setting search_path = public, pg_catalog pins the resolution.

BEGIN;

-- ============================================================
-- update_updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_catalog
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================
-- set_match_expiration
-- ============================================================
CREATE OR REPLACE FUNCTION public.set_match_expiration()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_catalog
AS $$
BEGIN
  IF NEW.expires_at IS NULL THEN
    NEW.expires_at := NEW.matched_at + INTERVAL '30 days';
  END IF;
  RETURN NEW;
END;
$$;

-- ============================================================
-- update_group_member_count
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_group_member_count()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_catalog
AS $$
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
$$;

-- ============================================================
-- expire_old_matches
-- ============================================================
CREATE OR REPLACE FUNCTION public.expire_old_matches(days_threshold integer DEFAULT 30)
RETURNS integer
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_catalog
AS $$
DECLARE
  affected_rows integer;
BEGIN
  UPDATE public.stable_matches
  SET status = 'expired'
  WHERE status = 'active'
    AND matched_at < NOW() - (days_threshold || ' days')::interval;

  GET DIAGNOSTICS affected_rows = ROW_COUNT;
  RETURN affected_rows;
END;
$$;

-- ============================================================
-- date_ranges_overlap
-- ============================================================
CREATE OR REPLACE FUNCTION public.date_ranges_overlap(
  start1 date,
  end1   date,
  start2 date,
  end2   date
)
RETURNS boolean
LANGUAGE plpgsql
IMMUTABLE
SECURITY INVOKER
SET search_path = public, pg_catalog
AS $$
BEGIN
    IF start1 IS NULL OR start2 IS NULL THEN
        RETURN TRUE;
    END IF;

    IF end1 IS NULL AND end2 IS NULL THEN
        RETURN TRUE;
    END IF;

    IF end1 IS NULL THEN
        RETURN start1 <= COALESCE(end2, start1);
    END IF;

    IF end2 IS NULL THEN
        RETURN start2 <= end1;
    END IF;

    RETURN start1 <= end2 AND start2 <= end1;
END;
$$;

COMMIT;
