-- Stable Matching Algorithm - Database Schema
-- Phase 0: Tables for Deferred Acceptance (Gale-Shapley) matching
-- 
-- NOTE: If tables already exist, use stable_matching_schema_migration.sql instead
-- This file assumes clean slate creation

-- =============================================================================
-- 1. Extend existing tables with new fields
-- =============================================================================

DO $$ 
BEGIN
  -- Check and add accepts_groups column
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' 
    AND table_name = 'listings' 
    AND column_name = 'accepts_groups'
  ) THEN
    ALTER TABLE public.listings ADD COLUMN accepts_groups boolean DEFAULT true;
    COMMENT ON COLUMN public.listings.accepts_groups IS 'Whether this listing accepts roommate groups (for stable matching)';
  END IF;

  -- Check and add max_occupancy column
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' 
    AND table_name = 'listings' 
    AND column_name = 'max_occupancy'
  ) THEN
    ALTER TABLE public.listings ADD COLUMN max_occupancy integer;
    COMMENT ON COLUMN public.listings.max_occupancy IS 'Maximum number of occupants allowed';
  END IF;
END $$;

-- =============================================================================
-- 2. Stable Matches Table - Stores matching results
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.stable_matches (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  diagnostics_id uuid,
  group_id text NOT NULL,
  listing_id text NOT NULL,
  group_score numeric NOT NULL,
  listing_score numeric NOT NULL,
  group_rank integer NOT NULL,
  listing_rank integer NOT NULL,
  matched_at timestamp with time zone NOT NULL DEFAULT now(),
  is_stable boolean NOT NULL DEFAULT true,
  status text NOT NULL DEFAULT 'active',
  expires_at timestamp with time zone,
  CONSTRAINT stable_matches_pkey PRIMARY KEY (id),
  CONSTRAINT stable_matches_diagnostics_id_fkey FOREIGN KEY (diagnostics_id) REFERENCES public.match_diagnostics(id) ON DELETE CASCADE,
  CONSTRAINT stable_matches_status_check CHECK (status IN ('active', 'accepted', 'rejected', 'expired'))
);

COMMENT ON TABLE public.stable_matches IS 'Stores stable matching results from Deferred Acceptance algorithm';
COMMENT ON COLUMN public.stable_matches.diagnostics_id IS 'Foreign key to match_diagnostics for this matching round';
COMMENT ON COLUMN public.stable_matches.group_score IS 'Score this group gave to the listing (0-1000)';
COMMENT ON COLUMN public.stable_matches.listing_score IS 'Score this listing gave to the group (0-1000)';
COMMENT ON COLUMN public.stable_matches.group_rank IS 'Rank of this listing in the groups preference list (1 = first choice)';
COMMENT ON COLUMN public.stable_matches.listing_rank IS 'Rank of this group in the listings preference list (1 = first choice)';
COMMENT ON COLUMN public.stable_matches.is_stable IS 'Whether this match is part of a stable matching';

-- Indexes for stable_matches
CREATE INDEX IF NOT EXISTS idx_stable_matches_group_id ON public.stable_matches(group_id);
CREATE INDEX IF NOT EXISTS idx_stable_matches_listing_id ON public.stable_matches(listing_id);
CREATE INDEX IF NOT EXISTS idx_stable_matches_diagnostics_id ON public.stable_matches(diagnostics_id);
CREATE INDEX IF NOT EXISTS idx_stable_matches_status ON public.stable_matches(status);
CREATE INDEX IF NOT EXISTS idx_stable_matches_matched_at ON public.stable_matches(matched_at);

-- =============================================================================
-- 3. Match Diagnostics Table - Stores metrics for each match round
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.match_diagnostics (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  city text NOT NULL,
  date_window_start date NOT NULL,
  date_window_end date NOT NULL,
  total_groups integer NOT NULL,
  total_listings integer NOT NULL,
  feasible_pairs integer NOT NULL DEFAULT 0,
  matched_groups integer NOT NULL,
  matched_listings integer NOT NULL,
  unmatched_groups integer NOT NULL,
  unmatched_listings integer NOT NULL,
  proposals_sent integer NOT NULL DEFAULT 0,
  proposals_rejected integer NOT NULL DEFAULT 0,
  iterations integer NOT NULL DEFAULT 0,
  avg_group_rank numeric NOT NULL DEFAULT 0,
  avg_listing_rank numeric NOT NULL DEFAULT 0,
  match_quality_score numeric NOT NULL DEFAULT 0,
  is_stable boolean NOT NULL DEFAULT false,
  stability_check_passed boolean NOT NULL DEFAULT false,
  executed_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT match_diagnostics_pkey PRIMARY KEY (id)
);

COMMENT ON TABLE public.match_diagnostics IS 'Diagnostics and metrics for each stable matching round';
COMMENT ON COLUMN public.match_diagnostics.feasible_pairs IS 'Number of feasible group-listing pairs before matching';
COMMENT ON COLUMN public.match_diagnostics.proposals_sent IS 'Total proposals sent during DA algorithm';
COMMENT ON COLUMN public.match_diagnostics.proposals_rejected IS 'Total proposals rejected during DA algorithm';
COMMENT ON COLUMN public.match_diagnostics.iterations IS 'Number of iterations the DA algorithm took';
COMMENT ON COLUMN public.match_diagnostics.avg_group_rank IS 'Average rank of matched listings in groups preference lists';
COMMENT ON COLUMN public.match_diagnostics.avg_listing_rank IS 'Average rank of matched groups in listings preference lists';
COMMENT ON COLUMN public.match_diagnostics.match_quality_score IS 'Overall match quality score (0-100)';
COMMENT ON COLUMN public.match_diagnostics.is_stable IS 'Whether the matching is stable (no blocking pairs)';
COMMENT ON COLUMN public.match_diagnostics.stability_check_passed IS 'Whether stability verification passed';

-- Indexes for match_diagnostics
CREATE INDEX IF NOT EXISTS idx_match_diagnostics_city ON public.match_diagnostics(city);
CREATE INDEX IF NOT EXISTS idx_match_diagnostics_executed_at ON public.match_diagnostics(executed_at);

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

-- Active stable matches (simple view for now, can be extended with joins later)
CREATE OR REPLACE VIEW public.v_active_stable_matches AS
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
FROM public.stable_matches sm
LEFT JOIN public.match_diagnostics md ON sm.diagnostics_id = md.id
WHERE sm.status = 'active';

COMMENT ON VIEW public.v_active_stable_matches IS 'All active stable matches with basic details';

-- =============================================================================
-- 6. Functions for match expiration
-- =============================================================================

-- Function to expire old matches
CREATE OR REPLACE FUNCTION expire_old_matches(days_threshold integer DEFAULT 30)
RETURNS integer AS $$
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
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_old_matches IS 'Marks matches older than N days as expired';

-- =============================================================================
-- 7. Trigger for auto-setting expires_at
-- =============================================================================

CREATE OR REPLACE FUNCTION set_match_expiration()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.expires_at IS NULL THEN
    NEW.expires_at := NEW.matched_at + INTERVAL '30 days';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_set_match_expiration ON public.stable_matches;
CREATE TRIGGER trigger_set_match_expiration
BEFORE INSERT ON public.stable_matches
FOR EACH ROW
EXECUTE FUNCTION set_match_expiration();

COMMENT ON FUNCTION set_match_expiration IS 'Automatically sets expires_at to 30 days after creation';
