-- Migration: Drop legacy stable-matching database objects
-- Date: 2026-04-06
--
-- This removes the old Gale-Shapley persistence layer now that Padly serves
-- direct ranked recommendations instead of stored stable matches.

BEGIN;

DROP VIEW IF EXISTS public.v_active_stable_matches;
DROP FUNCTION IF EXISTS public.expire_old_matches(integer);

DROP TABLE IF EXISTS public.stable_matches;
DROP TABLE IF EXISTS public.match_diagnostics;

COMMIT;
