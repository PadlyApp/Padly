create table if not exists public.user_interested_listings (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid not null references public.users(id) on delete cascade,
  listing_id text not null,
  source text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (actor_user_id, listing_id)
);

create index if not exists idx_user_interested_listings_actor_user_id
  on public.user_interested_listings (actor_user_id);

create index if not exists idx_user_interested_listings_created_at
  on public.user_interested_listings (created_at desc);

alter table public.user_interested_listings enable row level security;

drop policy if exists "Users can view own interested listings" on public.user_interested_listings;
create policy "Users can view own interested listings"
  on public.user_interested_listings
  for select
  using (
    exists (
      select 1
      from public.users u
      where u.id = actor_user_id
        and u.auth_id = auth.uid()
    )
  );

drop policy if exists "Users can insert own interested listings" on public.user_interested_listings;
create policy "Users can insert own interested listings"
  on public.user_interested_listings
  for insert
  with check (
    exists (
      select 1
      from public.users u
      where u.id = actor_user_id
        and u.auth_id = auth.uid()
    )
  );

drop policy if exists "Users can delete own interested listings" on public.user_interested_listings;
create policy "Users can delete own interested listings"
  on public.user_interested_listings
  for delete
  using (
    exists (
      select 1
      from public.users u
      where u.id = actor_user_id
        and u.auth_id = auth.uid()
    )
  );
