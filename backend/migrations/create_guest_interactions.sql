-- Migration: create guest_interactions table
-- Purpose: log anonymous behavioural events from unauthenticated (guest) users
--          for funnel analytics and understanding pre-signup drop-off.
--
-- Per project policy: never ALTER existing tables.
-- This is a brand-new companion table with no FK dependencies on user tables.

create table if not exists public.guest_interactions (
    id                   uuid primary key default gen_random_uuid(),
    guest_session_id     text             not null,
    event_type           text             not null,
    -- event_type values: swipe_right, swipe_left, listing_view,
    --                    signup_prompt_shown, signup_prompt_dismissed, signup_prompt_clicked
    listing_id           uuid             references public.listings(id) on delete set null,
    position_in_feed     int,
    guest_prefs_snapshot jsonb,           -- location + price snapshot at time of event
    device_context       jsonb,           -- device_type, os, browser, screen dimensions
    ip_hash              text,            -- first 16 hex chars of SHA-256(ip) for dedup only
    created_at           timestamptz      not null default now()
);

-- Session-level queries (e.g. reconstruct a guest journey)
create index if not exists idx_guest_interactions_session
    on public.guest_interactions (guest_session_id);

-- Time-range queries for funnel dashboards
create index if not exists idx_guest_interactions_created_at
    on public.guest_interactions (created_at);

-- Event-type aggregations
create index if not exists idx_guest_interactions_event_type
    on public.guest_interactions (event_type);

-- Lock the table down: the backend uses the service-role client which bypasses
-- RLS, so no explicit policies are needed. All direct client access is blocked.
alter table public.guest_interactions enable row level security;
