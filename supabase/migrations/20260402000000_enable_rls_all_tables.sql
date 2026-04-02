-- Migration: Enable RLS on all public tables and add safe policies
-- Date: 2026-04-02
--
-- Strategy:
--   The backend uses the service_role key for almost all writes/reads, which
--   bypasses RLS entirely. These policies therefore protect against:
--     1. Direct PostgREST calls with only the anon key (no JWT)
--     2. Direct PostgREST calls with a valid user JWT
--   The backend service-role paths are unaffected.

BEGIN;

-- ============================================================
-- GRANT schema/table access to roles used by PostgREST
-- ============================================================
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- ============================================================
-- users
-- ============================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Anyone (including anon) can read basic public profile info
DROP POLICY IF EXISTS "users_select_public" ON public.users;
CREATE POLICY "users_select_public"
  ON public.users FOR SELECT
  USING (true);

-- Only the owning user can update their own row
DROP POLICY IF EXISTS "users_update_own" ON public.users;
CREATE POLICY "users_update_own"
  ON public.users FOR UPDATE
  TO authenticated
  USING (auth.uid() = auth_id)
  WITH CHECK (auth.uid() = auth_id);

-- Only the owning user can delete their own row
DROP POLICY IF EXISTS "users_delete_own" ON public.users;
CREATE POLICY "users_delete_own"
  ON public.users FOR DELETE
  TO authenticated
  USING (auth.uid() = auth_id);

-- Insert is handled by the backend (service role) during signup
-- No anon/authenticated INSERT policy needed

-- ============================================================
-- listings
-- ============================================================
ALTER TABLE public.listings ENABLE ROW LEVEL SECURITY;

-- Anyone can read active listings
DROP POLICY IF EXISTS "listings_select_active" ON public.listings;
CREATE POLICY "listings_select_active"
  ON public.listings FOR SELECT
  USING (status = 'active' OR auth.uid() IS NOT NULL);

-- Authenticated users can insert their own listings
DROP POLICY IF EXISTS "listings_insert_own" ON public.listings;
CREATE POLICY "listings_insert_own"
  ON public.listings FOR INSERT
  TO authenticated
  WITH CHECK (
    host_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );

-- Authenticated users can update their own listings
DROP POLICY IF EXISTS "listings_update_own" ON public.listings;
CREATE POLICY "listings_update_own"
  ON public.listings FOR UPDATE
  TO authenticated
  USING (
    host_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  )
  WITH CHECK (
    host_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );

-- Authenticated users can delete their own listings
DROP POLICY IF EXISTS "listings_delete_own" ON public.listings;
CREATE POLICY "listings_delete_own"
  ON public.listings FOR DELETE
  TO authenticated
  USING (
    host_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );

-- ============================================================
-- listing_photos
-- ============================================================
ALTER TABLE public.listing_photos ENABLE ROW LEVEL SECURITY;

-- Anyone can read listing photos
DROP POLICY IF EXISTS "listing_photos_select_all" ON public.listing_photos;
CREATE POLICY "listing_photos_select_all"
  ON public.listing_photos FOR SELECT
  USING (true);

-- Only the listing owner can insert/update/delete photos
DROP POLICY IF EXISTS "listing_photos_write_own" ON public.listing_photos;
CREATE POLICY "listing_photos_write_own"
  ON public.listing_photos FOR ALL
  TO authenticated
  USING (
    listing_id IN (
      SELECT l.id FROM public.listings l
      JOIN public.users u ON l.host_user_id = u.id
      WHERE u.auth_id = auth.uid()
    )
  )
  WITH CHECK (
    listing_id IN (
      SELECT l.id FROM public.listings l
      JOIN public.users u ON l.host_user_id = u.id
      WHERE u.auth_id = auth.uid()
    )
  );

-- ============================================================
-- roommate_groups
-- ============================================================
ALTER TABLE public.roommate_groups ENABLE ROW LEVEL SECURITY;

-- Anyone can read active groups
DROP POLICY IF EXISTS "roommate_groups_select_active" ON public.roommate_groups;
CREATE POLICY "roommate_groups_select_active"
  ON public.roommate_groups FOR SELECT
  USING (status = 'active' OR auth.uid() IS NOT NULL);

-- Authenticated users can create groups
DROP POLICY IF EXISTS "roommate_groups_insert_own" ON public.roommate_groups;
CREATE POLICY "roommate_groups_insert_own"
  ON public.roommate_groups FOR INSERT
  TO authenticated
  WITH CHECK (
    creator_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );

-- Only the creator can update/delete their group
DROP POLICY IF EXISTS "roommate_groups_update_own" ON public.roommate_groups;
CREATE POLICY "roommate_groups_update_own"
  ON public.roommate_groups FOR UPDATE
  TO authenticated
  USING (
    creator_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  )
  WITH CHECK (
    creator_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "roommate_groups_delete_own" ON public.roommate_groups;
CREATE POLICY "roommate_groups_delete_own"
  ON public.roommate_groups FOR DELETE
  TO authenticated
  USING (
    creator_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );

-- ============================================================
-- group_members
-- ============================================================
ALTER TABLE public.group_members ENABLE ROW LEVEL SECURITY;

-- Members can read their own group memberships; group creators can read all members
DROP POLICY IF EXISTS "group_members_select" ON public.group_members;
CREATE POLICY "group_members_select"
  ON public.group_members FOR SELECT
  TO authenticated
  USING (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
    OR group_id IN (
      SELECT id FROM public.roommate_groups
      WHERE creator_user_id IN (
        SELECT id FROM public.users WHERE auth_id = auth.uid()
      )
    )
  );

-- Users can insert themselves into a group (invitations handled by service role)
DROP POLICY IF EXISTS "group_members_insert_own" ON public.group_members;
CREATE POLICY "group_members_insert_own"
  ON public.group_members FOR INSERT
  TO authenticated
  WITH CHECK (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- Users can update/delete their own membership
DROP POLICY IF EXISTS "group_members_update_own" ON public.group_members;
CREATE POLICY "group_members_update_own"
  ON public.group_members FOR UPDATE
  TO authenticated
  USING (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  )
  WITH CHECK (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

DROP POLICY IF EXISTS "group_members_delete_own" ON public.group_members;
CREATE POLICY "group_members_delete_own"
  ON public.group_members FOR DELETE
  TO authenticated
  USING (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- ============================================================
-- personal_preferences
-- ============================================================
ALTER TABLE public.personal_preferences ENABLE ROW LEVEL SECURITY;

-- Users can only read their own preferences
DROP POLICY IF EXISTS "personal_preferences_select_own" ON public.personal_preferences;
CREATE POLICY "personal_preferences_select_own"
  ON public.personal_preferences FOR SELECT
  TO authenticated
  USING (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- Users can insert/update/delete their own preferences
DROP POLICY IF EXISTS "personal_preferences_write_own" ON public.personal_preferences;
CREATE POLICY "personal_preferences_write_own"
  ON public.personal_preferences FOR ALL
  TO authenticated
  USING (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  )
  WITH CHECK (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- ============================================================
-- roommate_posts
-- ============================================================
ALTER TABLE public.roommate_posts ENABLE ROW LEVEL SECURITY;

-- Anyone can read active posts
DROP POLICY IF EXISTS "roommate_posts_select_active" ON public.roommate_posts;
CREATE POLICY "roommate_posts_select_active"
  ON public.roommate_posts FOR SELECT
  USING (status = 'active' OR auth.uid() IS NOT NULL);

-- Users can manage their own posts
DROP POLICY IF EXISTS "roommate_posts_write_own" ON public.roommate_posts;
CREATE POLICY "roommate_posts_write_own"
  ON public.roommate_posts FOR ALL
  TO authenticated
  USING (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  )
  WITH CHECK (
    user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- ============================================================
-- stable_matches
-- ============================================================
ALTER TABLE public.stable_matches ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read matches for their group or listing
-- stable_matches.group_id and listing_id are text columns, so cast uuid subquery results
DROP POLICY IF EXISTS "stable_matches_select_own" ON public.stable_matches;
CREATE POLICY "stable_matches_select_own"
  ON public.stable_matches FOR SELECT
  TO authenticated
  USING (
    group_id IN (
      SELECT gm.group_id::text FROM public.group_members gm
      JOIN public.users u ON gm.user_id = u.id
      WHERE u.auth_id = auth.uid()
    )
    OR listing_id IN (
      SELECT l.id::text FROM public.listings l
      JOIN public.users u ON l.host_user_id = u.id
      WHERE u.auth_id = auth.uid()
    )
  );

-- Writes are service-role only (no authenticated INSERT/UPDATE/DELETE policy)

-- ============================================================
-- match_diagnostics
-- ============================================================
ALTER TABLE public.match_diagnostics ENABLE ROW LEVEL SECURITY;

-- Only authenticated users can read diagnostics (admin/service role always bypasses)
DROP POLICY IF EXISTS "match_diagnostics_select_authenticated" ON public.match_diagnostics;
CREATE POLICY "match_diagnostics_select_authenticated"
  ON public.match_diagnostics FOR SELECT
  TO authenticated
  USING (true);

-- Writes are service-role only

-- ============================================================
-- roommate_intro_requests
-- ============================================================
ALTER TABLE public.roommate_intro_requests ENABLE ROW LEVEL SECURITY;

-- Users can read intro requests they sent or received
DROP POLICY IF EXISTS "roommate_intro_requests_select_own" ON public.roommate_intro_requests;
CREATE POLICY "roommate_intro_requests_select_own"
  ON public.roommate_intro_requests FOR SELECT
  TO authenticated
  USING (
    from_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
    OR to_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- Users can insert requests they initiate
DROP POLICY IF EXISTS "roommate_intro_requests_insert_own" ON public.roommate_intro_requests;
CREATE POLICY "roommate_intro_requests_insert_own"
  ON public.roommate_intro_requests FOR INSERT
  TO authenticated
  WITH CHECK (
    from_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- Users can update requests they are part of (e.g. accept/decline)
DROP POLICY IF EXISTS "roommate_intro_requests_update_own" ON public.roommate_intro_requests;
CREATE POLICY "roommate_intro_requests_update_own"
  ON public.roommate_intro_requests FOR UPDATE
  TO authenticated
  USING (
    from_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
    OR to_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  )
  WITH CHECK (
    from_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
    OR to_user_id IN (SELECT id FROM public.users WHERE auth_id = auth.uid())
  );

-- ============================================================
-- rentcast_sync_log (internal, no user access needed)
-- ============================================================
ALTER TABLE public.rentcast_sync_log ENABLE ROW LEVEL SECURITY;
-- No policies: only service_role can access this table

COMMIT;
