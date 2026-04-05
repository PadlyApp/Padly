-- Migration: Move extensions from public schema to extensions schema
-- Fixes Supabase Security Advisor warnings for public.cube and public.earthdistance

CREATE SCHEMA IF NOT EXISTS extensions;

ALTER EXTENSION cube SET SCHEMA extensions;
ALTER EXTENSION earthdistance SET SCHEMA extensions;
