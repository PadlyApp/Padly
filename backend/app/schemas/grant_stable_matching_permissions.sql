-- Grant Permissions for Stable Matching Tables
-- Run this after the migration script to enable API access

-- =============================================================================
-- Grant permissions on match_diagnostics table
-- =============================================================================

-- Grant full access to authenticated users (for now)
GRANT ALL ON public.match_diagnostics TO authenticated;
GRANT ALL ON public.match_diagnostics TO anon;
GRANT ALL ON public.match_diagnostics TO service_role;

-- Grant usage on the sequence (for UUID generation)
-- Note: gen_random_uuid() doesn't use a sequence, but good practice

-- =============================================================================
-- Grant permissions on stable_matches table
-- =============================================================================

GRANT ALL ON public.stable_matches TO authenticated;
GRANT ALL ON public.stable_matches TO anon;
GRANT ALL ON public.stable_matches TO service_role;

-- =============================================================================
-- Grant permissions on view
-- =============================================================================

GRANT SELECT ON public.v_active_stable_matches TO authenticated;
GRANT SELECT ON public.v_active_stable_matches TO anon;
GRANT SELECT ON public.v_active_stable_matches TO service_role;

-- =============================================================================
-- Grant permissions on functions
-- =============================================================================

GRANT EXECUTE ON FUNCTION expire_old_matches(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION expire_old_matches(integer) TO anon;
GRANT EXECUTE ON FUNCTION expire_old_matches(integer) TO service_role;

GRANT EXECUTE ON FUNCTION set_match_expiration() TO authenticated;
GRANT EXECUTE ON FUNCTION set_match_expiration() TO anon;
GRANT EXECUTE ON FUNCTION set_match_expiration() TO service_role;

-- =============================================================================
-- Done!
-- =============================================================================

SELECT 'Permissions granted successfully!' as status;
