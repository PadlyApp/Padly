# Real Listings Import

## Goal

Replace Padly's fake inventory with scraped multi-bedroom listings that match the roommate-first product shape:

- 2 to 5 bedrooms only
- GTA / NYC / SF buckets
- rich description + amenities + house rules
- listing photos imported into `listing_photos`

## 1. Export Apify datasets

Run the scrape separately and export one dataset file per market. Name the files so the importer can infer the metro bucket:

- `toronto.json` or `gta.json`
- `nyc.json` or `new_york.json`
- `sf.json` or `san_francisco.json`

JSON arrays and JSONL exports are both supported.

## 2. Dry-run the importer

From [backend](/Users/yousefmaher/Padly/backend):

```bash
PYTHONPATH=. ./venv/bin/python -m app.scripts.import_apify_listings \
  ../data/gta.json \
  ../data/nyc.json \
  ../data/sf.json \
  --dry-run
```

The script will:

- infer the market bucket from the file name and listing location
- keep at most 135 listings per metro bucket
- drop listings outside the 2 to 5 bedroom range
- compute `price_per_room`
- default the host to the most common current `host_user_id` unless `--host-user-id` is provided

## 3. Replace the current inventory

```bash
PYTHONPATH=. ./venv/bin/python -m app.scripts.import_apify_listings \
  ../data/gta.json \
  ../data/nyc.json \
  ../data/sf.json \
  --wipe-existing
```

`--wipe-existing` deletes:

- `stable_matches`
- `listing_photos`
- `listings`

before loading the new inventory.

## Notes

- Discover and listing detail now expose `images` by hydrating `listing_photos`.
- The importer stores `price_per_room` on `listings` for roommate-oriented pricing.
- If you want a specific host owner for the imported listings, pass `--host-user-id <users.id>`.
