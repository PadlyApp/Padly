# Backend Changes - 2026-03-30

This document captures the backend-heavy work completed for the current `Arhum-frontEnd-Rework` branch.

## 1. Group sizing

- Removed the hard default of `2` members for roommate groups.
- Made `target_group_size` optional so groups can be unlimited.
- Updated backend validation so join requests only enforce capacity when a limit is explicitly set.
- Added and pushed the Supabase migration:
  - `supabase/migrations/20260330170000_dynamic_group_sizing.sql`

## 2. Real listings import pipeline

- Added an import script for Apify JSON / JSONL exports:
  - `app/scripts/import_apify_listings.py`
- Added a reusable listing payload hydrator:
  - `app/services/listing_payloads.py`
- Added runbook documentation:
  - `REAL_LISTINGS_IMPORT.md`
- Added `price_per_room` support and pushed the Supabase migration:
  - `supabase/migrations/20260330173000_add_price_per_room_to_listings.sql`

### Import behavior

- Keeps only multi-bedroom inventory relevant for Padly.
- Computes `price_per_room`.
- Imports listing photos into `listing_photos`.
- Dedupes against already-imported DB listings.
- Supports append-only imports.
- Retries transient Supabase `5xx` / `502` failures during inserts.

## 3. Inventory refresh

- Imported real GTA, NYC, and Bay Area inventory from Apify exports.
- Removed the old fake listings from the database after the real imports were verified.
- Expanded inventory heavily toward larger shared units.

Current active listing snapshot after the expansion:

- Total active listings: `2876`
- Bedroom mix:
  - `2 bed`: `275`
  - `3 bed`: `1790`
  - `4 bed`: `653`
  - `5 bed`: `158`
- Photos stored: `30740`

Approximate metro split:

- GTA: `1183`
- NYC: `761`
- Bay Area: `871`

## 4. Recommendation and filtering fixes

- Recommendation hard constraints now normalize:
  - country
  - state / province
  - city names with neighborhood suffixes
- Removed the old deposit fallback that treated monthly rent as deposit.
- Stopped forcing imported listings to `12` month leases when the data does not specify that.
- Added pagination support to recommendations so `Discover` can keep loading more inventory.

## 5. Metro-aware location matching

- Added shared location normalization in:
  - `app/services/location_matching.py`
- Wired it into:
  - recommender hard constraints
  - group listing feeds
  - stable matching hard filters
  - group rematching

This means exact-string city matching is no longer required. Examples:

- `Toronto` now matches Toronto neighborhood-style cities and nearby GTA cities like `Mississauga`, `Vaughan`, `Markham`, and `Richmond Hill`.
- `New York` now matches borough inventory like `Brooklyn`, `Queens`, and `Bronx`.
- `San Francisco` now matches broader Bay Area inventory like `Oakland`, `Berkeley`, `San Jose`, `Fremont`, `Mountain View`, and `Palo Alto`.

## 6. Frontend behavior that depends on backend changes

- `Discover` now paginates recommendations instead of exhausting after one batch.
- `Discover` filters previously swiped listings after refresh.
- `Matches` now uses the recommendation pipeline instead of only local liked listings.
- `Matches` requests a larger ranked result set.
- Listing image hydration now supports gallery rendering when multiple photos exist in the database.

## 7. Validation performed

- Supabase migrations were pushed successfully.
- Listing counts and bedroom distributions were verified directly against the live Supabase project.
- Backend Python files touched in the latest pass were syntax-checked with `py_compile`.

## 8. Remaining caveats

- The saved Keras two-tower artifact still fails to deserialize cleanly in this environment, so recommendation calls currently fall back to the heuristic / blended ranking path instead of live model inference.
- Group feeds and stable matching are now metro-aware, but any downstream analytics or reporting code that still assumes exact city equality should be reviewed separately.
