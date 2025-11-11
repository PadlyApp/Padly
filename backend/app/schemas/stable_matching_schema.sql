-- Stable Matching Algorithm - Database Schema
-- Phase 0: Tables for Deferred Acceptance (Gale-Shapley) matching

-- =============================================================================
-- 1. Extend existing tables with new fields
-- =============================================================================

-- Add fields to listings table
ALTER TABLE public.listings 
ADD COLUMN IF NOT EXISTS accepts_groups boolean DEFAULT true,
ADD COLUMN IF NOT EXISTS max_occupancy integer;

COMMENT ON COLUMN public.listings.accepts_groups IS 'Whether this listing accepts roommate groups (for stable matching)';
COMMENT ON COLUMN public.listings.max_occupancy IS 'Maximum number of occupants allowed';

-- =============================================================================
-- 2. Stable Matches Table - Stores matching results
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.stable_matches (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  group_id uuid NOT NULL,
  listing_id uuid NOT NULL,
  match_round_id uuid NOT NULL,
  orientation text NOT NULL DEFAULT 'groups-proposing',
  city text NOT NULL,
  match_window_start date NOT NULL,
  match_window_end date NOT NULL,
  group_rank_of_listing integer NOT NULL,
  listing_rank_of_group integer NOT NULL,
  group_score numeric NOT NULL,
  listing_score numeric NOT NULL,
  explanation_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  status text NOT NULL DEFAULT 'active',
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  expires_at timestamp with time zone,
  CONSTRAINT stable_matches_pkey PRIMARY KEY (id),
  CONSTRAINT stable_matches_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.roommate_groups(id) ON DELETE CASCADE,
  CONSTRAINT stable_matches_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.listings(id) ON DELETE CASCADE,
  CONSTRAINT stable_matches_status_check CHECK (status IN ('active', 'accepted', 'rejected', 'expired'))
);

COMMENT ON TABLE public.stable_matches IS 'Stores stable matching results from Deferred Acceptance algorithm';
COMMENT ON COLUMN public.stable_matches.orientation IS 'Which side proposes: groups-proposing or listings-proposing';
COMMENT ON COLUMN public.stable_matches.group_rank_of_listing IS 'What rank was this listing in the groups preference list (1 = first choice)';
COMMENT ON COLUMN public.stable_matches.listing_rank_of_group IS 'What rank was this group in the listings preference list (1 = first choice)';
COMMENT ON COLUMN public.stable_matches.explanation_reasons IS 'Array of human-readable reasons for this match';

-- Indexes for stable_matches
CREATE INDEX IF NOT EXISTS idx_stable_matches_group_id_status ON public.stable_matches(group_id, status);
CREATE INDEX IF NOT EXISTS idx_stable_matches_listing_id_status ON public.stable_matches(listing_id, status);
CREATE INDEX IF NOT EXISTS idx_stable_matches_round_id ON public.stable_matches(match_round_id);
CREATE INDEX IF NOT EXISTS idx_stable_matches_city ON public.stable_matches(city);
CREATE INDEX IF NOT EXISTS idx_stable_matches_created_at ON public.stable_matches(created_at);

-- =============================================================================
-- 3. Match Diagnostics Table - Stores metrics for each match round
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.match_diagnostics (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  match_round_id uuid NOT NULL UNIQUE,
  city text NOT NULL,
  window_start date NOT NULL,
  window_end date NOT NULL,
  total_groups integer NOT NULL,
  total_listings integer NOT NULL,
  matched_groups integer NOT NULL,
  matched_listings integer NOT NULL,
  match_rate_pct numeric NOT NULL,
  median_group_rank integer,
  top_3_rate_pct numeric,
  unmatched_reasons jsonb NOT NULL DEFAULT '{}'::jsonb,
  avg_verification_rate numeric,
  algorithm_version text NOT NULL DEFAULT 'DA_v1',
  run_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT match_diagnostics_pkey PRIMARY KEY (id)
);

COMMENT ON TABLE public.match_diagnostics IS 'Diagnostics and metrics for each stable matching round';
COMMENT ON COLUMN public.match_diagnostics.match_rate_pct IS 'Percentage of groups that got matched';
COMMENT ON COLUMN public.match_diagnostics.median_group_rank IS 'Median rank of matched listings in groups preference lists';
COMMENT ON COLUMN public.match_diagnostics.top_3_rate_pct IS 'Percentage of groups that got one of their top 3 choices';
COMMENT ON COLUMN public.match_diagnostics.unmatched_reasons IS 'Breakdown of why groups didnt match: {location: N, date: N, price: N, ...}';

-- Indexes for match_diagnostics
CREATE INDEX IF NOT EXISTS idx_match_diagnostics_city ON public.match_diagnostics(city);
CREATE INDEX IF NOT EXISTS idx_match_diagnostics_run_at ON public.match_diagnostics(run_at);

-- =============================================================================
-- 4. Additional indexes on existing tables for performance
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_listings_city_status ON public.listings(city, status);
CREATE INDEX IF NOT EXISTS idx_listings_property_type_bedrooms ON public.listings(property_type, number_of_bedrooms);
CREATE INDEX IF NOT EXISTS idx_roommate_groups_city_status_size ON public.roommate_groups(target_city, status, target_group_size);
CREATE INDEX IF NOT EXISTS idx_roommate_groups_move_in_date ON public.roommate_groups(target_move_in_date);

-- =============================================================================
-- 5. Views for easier querying
-- =============================================================================

-- Active stable matches with full details
CREATE OR REPLACE VIEW public.v_active_stable_matches AS
SELECT 
  sm.id,
  sm.match_round_id,
  sm.group_id,
  sm.listing_id,
  sm.city,
  sm.group_rank_of_listing,
  sm.listing_rank_of_group,
  sm.group_score,
  sm.listing_score,
  sm.explanation_reasons,
  sm.created_at,
  sm.expires_at,
  rg.group_name,
  rg.target_move_in_date,
  rg.budget_per_person_min,
  rg.budget_per_person_max,
  l.title AS listing_title,
  l.price_per_month,
  l.available_from,
  l.number_of_bedrooms,
  l.furnished
FROM public.stable_matches sm
JOIN public.roommate_groups rg ON sm.group_id = rg.id
JOIN public.listings l ON sm.listing_id = l.id
WHERE sm.status = 'active';

COMMENT ON VIEW public.v_active_stable_matches IS 'All active stable matches with group and listing details';

-- =============================================================================
-- 6. Functions for match expiration
-- =============================================================================

-- Function to expire old matches
CREATE OR REPLACE FUNCTION expire_old_stable_matches(expiration_days integer DEFAULT 7)
RETURNS integer AS $$
DECLARE
  affected_rows integer;
BEGIN
  UPDATE public.stable_matches
  SET status = 'expired'
  WHERE status = 'active'
    AND created_at < NOW() - (expiration_days || ' days')::interval
    AND expires_at IS NULL;
  
  GET DIAGNOSTICS affected_rows = ROW_COUNT;
  RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_old_stable_matches IS 'Marks matches older than N days as expired';

-- =============================================================================
-- 7. Trigger for auto-setting expires_at
-- =============================================================================

CREATE OR REPLACE FUNCTION set_match_expiration()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.expires_at IS NULL THEN
    NEW.expires_at := NEW.created_at + INTERVAL '7 days';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_match_expiration
BEFORE INSERT ON public.stable_matches
FOR EACH ROW
EXECUTE FUNCTION set_match_expiration();

COMMENT ON FUNCTION set_match_expiration IS 'Automatically sets expires_at to 7 days after creation';
