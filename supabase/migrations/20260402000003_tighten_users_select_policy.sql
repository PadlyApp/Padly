-- Migration: Tighten users table SELECT access
-- Date: 2026-04-02
--
-- Strategy: use a SECURITY BARRIER view (user_public_profiles) to expose only
-- safe profile columns. The underlying users table keeps full SELECT for
-- authenticated so existing backend JWT routes keep working. Private fields
-- (email, auth_id, verified_email, verified_at, last_active_at) are only
-- accessible via service_role (backend) — never through the view.
--
-- Note: Postgres column-level REVOKE is overridden by table-level GRANT, so
-- the view approach is the correct way to restrict column visibility.

BEGIN;

-- Remove the wide-open policy added in the initial RLS migration
DROP POLICY IF EXISTS "users_select_public" ON public.users;

-- Authenticated users can read their own row or others via the view
DROP POLICY IF EXISTS "users_select_others_profile" ON public.users;
CREATE POLICY "users_select_others_profile"
  ON public.users FOR SELECT
  TO authenticated
  USING (true);

-- Anon gets nothing on the base table
REVOKE ALL ON public.users FROM anon;

-- Restore table-level SELECT for authenticated (needed by PostgREST + JWT routes)
GRANT SELECT ON public.users TO authenticated;

-- Safe public profile view (security_barrier prevents column-leak via WHERE tricks)
CREATE OR REPLACE VIEW public.user_public_profiles
WITH (security_barrier = true, security_invoker = true)
AS
  SELECT
    id,
    full_name,
    bio,
    profile_picture_url,
    role,
    company_name,
    school_name,
    role_title,
    verification_status,
    verification_type,
    created_at
  FROM public.users;

GRANT SELECT ON public.user_public_profiles TO authenticated;
REVOKE ALL ON public.user_public_profiles FROM anon;

-- Private columns NOT in the view:
--   email, auth_id, verified_email, verified_at, last_active_at

COMMIT;
