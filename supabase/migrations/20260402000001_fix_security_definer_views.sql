-- Migration: Remove SECURITY DEFINER from public views
-- Date: 2026-04-02
--
-- SECURITY DEFINER views run with the permissions of the view creator
-- (usually postgres/superuser), bypassing RLS for all callers.
-- Recreating them without SECURITY DEFINER makes them run with the
-- calling role's permissions, so RLS is properly enforced.

BEGIN;

-- ============================================================
-- active_groups_view
-- ============================================================
DROP VIEW IF EXISTS public.active_groups_view;
CREATE VIEW public.active_groups_view AS
  SELECT
    rg.id,
    rg.creator_user_id,
    rg.group_name,
    rg.description,
    rg.target_city,
    rg.budget_per_person_min,
    rg.budget_per_person_max,
    rg.target_move_in_date,
    rg.target_group_size,
    rg.status,
    rg.created_at,
    rg.updated_at,
    u.full_name AS creator_name,
    u.verification_status AS creator_verification,
    COALESCE(member_count.count, 0::bigint) AS current_member_count
  FROM roommate_groups rg
  JOIN users u ON rg.creator_user_id = u.id
  LEFT JOIN (
    SELECT group_id, count(*) AS count
    FROM group_members
    GROUP BY group_id
  ) member_count ON rg.id = member_count.group_id
  WHERE rg.status = 'active'::post_status;

GRANT SELECT ON public.active_groups_view TO authenticated, service_role;

-- ============================================================
-- active_listings_view
-- ============================================================
DROP VIEW IF EXISTS public.active_listings_view;
CREATE VIEW public.active_listings_view AS
  SELECT
    l.id,
    l.host_user_id,
    l.status,
    l.title,
    l.description,
    l.property_type,
    l.lease_type,
    l.lease_duration_months,
    l.number_of_bedrooms,
    l.number_of_bathrooms,
    l.area_sqft,
    l.furnished,
    l.price_per_month,
    l.utilities_included,
    l.deposit_amount,
    l.address_line_1,
    l.address_line_2,
    l.city,
    l.state_province,
    l.postal_code,
    l.country,
    l.latitude,
    l.longitude,
    l.available_from,
    l.available_to,
    l.amenities,
    l.house_rules,
    l.shared_spaces,
    l.view_count,
    l.created_at,
    l.updated_at,
    u.full_name AS host_name,
    u.company_name AS host_company,
    u.school_name AS host_school,
    u.verification_status AS host_verification,
    COALESCE(photo_count.count, 0::bigint) AS photo_count
  FROM listings l
  JOIN users u ON l.host_user_id = u.id
  LEFT JOIN (
    SELECT listing_id, count(*) AS count
    FROM listing_photos
    GROUP BY listing_id
  ) photo_count ON l.id = photo_count.listing_id
  WHERE l.status = 'active'::listing_status;

GRANT SELECT ON public.active_listings_view TO authenticated, service_role;

-- ============================================================
-- active_roommate_posts_view
-- ============================================================
DROP VIEW IF EXISTS public.active_roommate_posts_view;
CREATE VIEW public.active_roommate_posts_view AS
  SELECT
    rp.id,
    rp.user_id,
    rp.status,
    rp.title,
    rp.description,
    rp.target_city,
    rp.preferred_neighborhoods,
    rp.budget_min,
    rp.budget_max,
    rp.move_in_date,
    rp.lease_duration_months,
    rp.looking_for_property_type,
    rp.looking_for_roommates,
    rp.preferred_roommate_count,
    rp.view_count,
    rp.created_at,
    rp.updated_at,
    u.full_name,
    u.profile_picture_url,
    u.company_name,
    u.school_name,
    u.role_title,
    u.verification_status,
    pp.lifestyle_preferences
  FROM roommate_posts rp
  JOIN users u ON rp.user_id = u.id
  LEFT JOIN personal_preferences pp ON u.id = pp.user_id
  WHERE rp.status = 'active'::post_status;

GRANT SELECT ON public.active_roommate_posts_view TO authenticated, service_role;

-- ============================================================
-- v_active_stable_matches
-- ============================================================
DROP VIEW IF EXISTS public.v_active_stable_matches;
CREATE VIEW public.v_active_stable_matches AS
  SELECT
    sm.id,
    sm.diagnostics_id,
    sm.group_id,
    sm.listing_id,
    sm.group_score,
    sm.listing_score,
    sm.group_rank,
    sm.listing_rank,
    sm.matched_at,
    sm.is_stable,
    sm.expires_at,
    md.city
  FROM stable_matches sm
  LEFT JOIN match_diagnostics md ON sm.diagnostics_id = md.id
  WHERE sm.status = 'active'::text;

GRANT SELECT ON public.v_active_stable_matches TO authenticated, service_role;

-- ============================================================
-- verified_renters
-- ============================================================
DROP VIEW IF EXISTS public.verified_renters;
CREATE VIEW public.verified_renters AS
  SELECT
    u.id,
    u.full_name,
    u.profile_picture_url,
    u.company_name,
    u.school_name,
    u.role_title,
    u.verification_status,
    u.verification_type,
    pp.target_city,
    pp.budget_min,
    pp.budget_max,
    pp.move_in_date,
    pp.lifestyle_preferences,
    u.created_at
  FROM users u
  LEFT JOIN personal_preferences pp ON u.id = pp.user_id
  WHERE u.role = 'renter'::user_role
    AND u.verification_status = ANY (ARRAY[
      'email_verified'::verification_status,
      'admin_verified'::verification_status
    ]);

GRANT SELECT ON public.verified_renters TO authenticated, service_role;

-- Explicitly mark all views as SECURITY INVOKER so RLS of the calling role is enforced
ALTER VIEW public.active_groups_view SET (security_invoker = true);
ALTER VIEW public.active_listings_view SET (security_invoker = true);
ALTER VIEW public.active_roommate_posts_view SET (security_invoker = true);
ALTER VIEW public.v_active_stable_matches SET (security_invoker = true);
ALTER VIEW public.verified_renters SET (security_invoker = true);

COMMIT;
