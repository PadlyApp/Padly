"""
Import Padly-ready listings from exported Apify JSON/JSONL datasets.

Usage:
  cd backend
  PYTHONPATH=. ./venv/bin/python -m app.scripts.import_apify_listings \
    data/gta.json data/nyc.json data/sf.json \
    --wipe-existing
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.db import supabase_admin
from postgrest.exceptions import APIError


CITY_BUCKET_ALIASES = {
    "gta": "toronto",
    "greater_toronto_area": "toronto",
    "toronto": "toronto",
    "downtown_toronto": "toronto",
    "north_york": "toronto",
    "mississauga": "toronto",
    "nyc": "new_york",
    "new_york": "new_york",
    "brooklyn": "new_york",
    "manhattan": "new_york",
    "williamsburg": "new_york",
    "bushwick": "new_york",
    "east_village": "new_york",
    "lower_east_side": "new_york",
    "sf": "san_francisco",
    "san_francisco": "san_francisco",
    "berkeley": "san_francisco",
    "soma": "san_francisco",
    "mission": "san_francisco",
}

BUCKET_DEFAULTS = {
    "toronto": {"city": "Toronto", "state_province": "Ontario", "country": "Canada"},
    "new_york": {"city": "New York", "state_province": "New York", "country": "USA"},
    "san_francisco": {"city": "San Francisco", "state_province": "California", "country": "USA"},
}


@dataclass
class PreparedListing:
    listing: Dict[str, Any]
    photos: List[Dict[str, Any]]
    bucket: str


def _strip_html(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _flatten_strings(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _clean_text(value)
        return [text] if text else []
    if isinstance(value, dict):
        out: List[str] = []
        for item in value.values():
            out.extend(_flatten_strings(item))
        return out
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            out.extend(_flatten_strings(item))
        return out
    text = _clean_text(value)
    return [text] if text else []


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        cleaned = re.sub(r"[^\d.\-]", "", cleaned)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _to_int(value: Any) -> Optional[int]:
    number = _to_float(value)
    if number is None:
        return None
    return int(round(number))


def _extract_numbers(value: Any) -> List[float]:
    if value is None:
        return []
    text = str(value)
    return [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]


def _parse_bedroom_value(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    numbers = _extract_numbers(value)
    if not numbers:
        return None
    return int(round(sum(numbers)))


def _parse_area_sqft(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip().lower()
    numbers = _extract_numbers(text)
    if not numbers:
        return None
    amount = numbers[0]
    if "m2" in text or "m²" in text or "sqm" in text:
        return int(round(amount * 10.7639))
    return int(round(amount))


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _deep_get(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _load_records(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text().strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError(f"Unsupported dataset shape in {path}")


def _infer_bucket(path: Path, raw: Dict[str, Any]) -> Optional[str]:
    candidates = [
        path.stem.lower(),
        _clean_text(_deep_get(raw, "address", "city")) or "",
        _clean_text(raw.get("city")) or "",
        _clean_text(_deep_get(raw, "location", "city")) or "",
        _clean_text(_deep_get(raw, "address", "suburb")) or "",
        _clean_text(_deep_get(raw, "location", "neighborhood")) or "",
    ]

    for candidate in candidates:
        normalized = _normalize_key(candidate)
        for alias, bucket in CITY_BUCKET_ALIASES.items():
            if alias in normalized:
                return bucket
    return None


def _extract_title(raw: Dict[str, Any]) -> Optional[str]:
    return _clean_text(
        _first_non_empty(
            raw.get("name"),
            raw.get("title"),
            raw.get("headline"),
            _deep_get(raw, "listing", "name"),
            _deep_get(raw, "address", "streetAddress"),
            _deep_get(raw, "Property", "Address", "AddressText"),
        )
    )


def _extract_description(raw: Dict[str, Any]) -> Optional[str]:
    chunks: List[str] = []
    for candidate in (
        raw.get("description"),
        raw.get("summary"),
        raw.get("PublicRemarks"),
        raw.get("descriptionHtml"),
        _deep_get(raw, "description", "html"),
        _deep_get(raw, "description", "text"),
        _deep_get(raw, "listing", "description"),
    ):
        if candidate is None:
            continue
        text = _strip_html(candidate) if "<" in str(candidate) else _clean_text(candidate)
        if text:
            chunks.append(text)

    amenities = _extract_amenities(raw)
    if amenities:
        chunks.append("Amenities: " + ", ".join(sorted(amenities.keys())[:20]))

    rules = _extract_house_rules(raw)
    if rules:
        chunks.append("House rules: " + rules)

    if not chunks:
        property_type = _clean_text(
            _first_non_empty(
                raw.get("propertyType"),
                _deep_get(raw, "Property", "Type"),
                _deep_get(raw, "Building", "Type"),
            )
        )
        bedrooms = _extract_bedrooms(raw)
        bathrooms = _extract_bathrooms(raw)
        address = _clean_text(
            _first_non_empty(
                _deep_get(raw, "address", "streetAddress"),
                _deep_get(raw, "Property", "Address", "AddressText"),
            )
        )
        facts = []
        if property_type:
            facts.append(property_type)
        if bedrooms is not None:
            facts.append(f"{bedrooms} bedrooms")
        if bathrooms is not None:
            facts.append(f"{bathrooms:g} bathrooms")
        if address:
            facts.append(address)
        broker = _clean_text(_deep_get(raw, "propertyDisplayRules", "mls", "brokerName"))
        if broker:
            facts.append(f"Listed by {broker}")
        if facts:
            chunks.append(". ".join(facts) + ".")

    deduped: List[str] = []
    seen = set()
    for chunk in chunks:
        key = chunk.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return "\n\n".join(deduped) if deduped else None


def _extract_price(raw: Dict[str, Any]) -> Optional[float]:
    candidates = [
        _deep_get(raw, "pricing", "rate", "amount"),
        _deep_get(raw, "pricing", "price", "amount"),
        _deep_get(raw, "pricing", "monthly", "amount"),
        _deep_get(raw, "price", "amount"),
        _deep_get(raw, "price", "value"),
        _deep_get(raw, "rental", "baseRent"),
        _deep_get(raw, "hdpView", "price"),
        _deep_get(raw, "Property", "LeaseRentUnformattedValue"),
        raw.get("price"),
        raw.get("pricePerMonth"),
        raw.get("monthlyPrice"),
    ]
    for candidate in candidates:
        value = _to_float(candidate)
        if value and value > 0:
            return value
    return None


def _extract_bedrooms(raw: Dict[str, Any]) -> Optional[int]:
    for candidate in (
        raw.get("bedrooms"),
        raw.get("bedroomCount"),
        _deep_get(raw, "Building", "Bedrooms"),
        _deep_get(raw, "details", "bedrooms"),
        _deep_get(raw, "rooms", "bedrooms"),
    ):
        value = _parse_bedroom_value(candidate)
        if value is not None:
            return value
    return None


def _extract_bathrooms(raw: Dict[str, Any]) -> Optional[float]:
    for candidate in (
        raw.get("bathrooms"),
        raw.get("bathroomCount"),
        _deep_get(raw, "Building", "BathroomTotal"),
        _deep_get(raw, "details", "bathrooms"),
        _deep_get(raw, "rooms", "bathrooms"),
    ):
        value = _to_float(candidate)
        if value is not None:
            return value
    return None


def _extract_area(raw: Dict[str, Any]) -> Optional[int]:
    for candidate in (
        raw.get("areaSqft"),
        raw.get("squareFeet"),
        raw.get("area"),
        _deep_get(raw, "Building", "SizeInterior"),
        _deep_get(raw, "details", "areaSqft"),
    ):
        value = _parse_area_sqft(candidate)
        if value is not None:
            return value
    for measurement in _deep_get(raw, "Building", "FloorAreaMeasurements") or []:
        value = _parse_area_sqft(
            _first_non_empty(
                measurement.get("AreaUnformatted"),
                measurement.get("Area"),
            )
        )
        if value is not None:
            return value
    return None


def _extract_amenities(raw: Dict[str, Any]) -> Dict[str, bool]:
    parsed: Dict[str, bool] = {}
    candidates = [
        raw.get("amenities"),
        raw.get("amenityGroups"),
        _deep_get(raw, "Building", "Ammenities"),
        _deep_get(raw, "Property", "AmmenitiesNearBy"),
        _deep_get(raw, "Property", "ParkingType"),
        raw.get("propertyType"),
        _deep_get(raw, "Property", "Type"),
        _deep_get(raw, "Building", "Type"),
        _deep_get(raw, "listing", "amenities"),
        _deep_get(raw, "factsAndFeatures"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key, value in candidate.items():
                if isinstance(value, bool):
                    parsed[_normalize_key(str(key))] = value
                else:
                    for item in _flatten_strings(value):
                        parsed[_normalize_key(item)] = True
        elif isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, dict):
                    name = _first_non_empty(item.get("title"), item.get("name"), item.get("label"))
                    available = item.get("available")
                    if name:
                        parsed[_normalize_key(str(name))] = bool(True if available is None else available)
                else:
                    for value in _flatten_strings(item):
                        parsed[_normalize_key(value)] = True
        elif isinstance(candidate, str):
            for value in re.split(r"[,/;|]+", candidate):
                text = _clean_text(value)
                if text:
                    parsed[_normalize_key(text)] = True
    return {key: value for key, value in parsed.items() if key}


def _extract_house_rules(raw: Dict[str, Any]) -> Optional[str]:
    rules = []
    for candidate in (
        raw.get("houseRules"),
        raw.get("rules"),
        _deep_get(raw, "description", "houseRules"),
    ):
        rules.extend(_flatten_strings(candidate))
    if not rules:
        return None
    deduped = list(dict.fromkeys(rules))
    return "; ".join(deduped)


def _extract_images(raw: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for candidate in (
        raw.get("images"),
        raw.get("photos"),
        raw.get("pictures"),
        _deep_get(raw, "Property", "Photo"),
        _deep_get(raw, "media", "allPropertyPhotos", "highResolution"),
        _deep_get(raw, "listing", "images"),
    ):
        if isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict):
                    url = _first_non_empty(
                        item.get("url"),
                        item.get("HighResPath"),
                        item.get("MedResPath"),
                        item.get("LowResPath"),
                        item.get("large"),
                        item.get("original"),
                        item.get("src"),
                    )
                    if url:
                        urls.append(str(url))
        elif isinstance(candidate, dict):
            url = _first_non_empty(
                candidate.get("highResolutionLink"),
                candidate.get("url"),
            )
            if url:
                urls.append(str(url))
    return list(dict.fromkeys([url for url in urls if url]))


def _parse_realtor_address(raw: Dict[str, Any]) -> Dict[str, Optional[str]]:
    address_text = _clean_text(_deep_get(raw, "Property", "Address", "AddressText"))
    if not address_text:
        return {
            "address_line_1": None,
            "city": None,
            "state_province": None,
            "postal_code": _clean_text(raw.get("PostalCode")),
        }

    line_1 = address_text
    city = None
    state = _clean_text(raw.get("ProvinceName"))
    postal_code = _clean_text(raw.get("PostalCode"))

    if "|" in address_text:
        line_1, suffix = [part.strip() for part in address_text.split("|", 1)]
        city_match = re.match(r"([^,]+),\s*([A-Za-z .'-]+)\s+([A-Za-z]\d[A-Za-z]\d[A-Za-z]\d)", suffix)
        if city_match:
            city = _clean_text(city_match.group(1))
            state = _clean_text(city_match.group(2))
            postal_code = _clean_text(city_match.group(3))
        else:
            city = _clean_text(suffix.split(",")[0])

    return {
        "address_line_1": _clean_text(line_1),
        "city": city,
        "state_province": state,
        "postal_code": postal_code,
    }


def _extract_location(raw: Dict[str, Any], bucket: str) -> Dict[str, Optional[str]]:
    defaults = BUCKET_DEFAULTS[bucket]
    city = _clean_text(
        _first_non_empty(
            _deep_get(raw, "address", "city"),
            _parse_realtor_address(raw).get("city"),
            raw.get("city"),
            _deep_get(raw, "location", "city"),
        )
    ) or defaults["city"]

    state = _clean_text(
        _first_non_empty(
            _deep_get(raw, "address", "state"),
            _parse_realtor_address(raw).get("state_province"),
            raw.get("state"),
            _deep_get(raw, "location", "state"),
        )
    ) or defaults["state_province"]

    country = _clean_text(
        _first_non_empty(
                _deep_get(raw, "address", "country"),
                raw.get("country"),
                _deep_get(raw, "location", "country"),
            )
        ) or ("Canada" if raw.get("ProvinceName") else defaults["country"])

    realtor_address = _parse_realtor_address(raw)

    return {
        "city": city,
        "state_province": state,
        "country": country,
        "address_line_1": _clean_text(
            _first_non_empty(
                _deep_get(raw, "address", "street"),
                _deep_get(raw, "address", "streetAddress"),
                realtor_address.get("address_line_1"),
                raw.get("address"),
            )
        ),
        "postal_code": _clean_text(
            _first_non_empty(
                _deep_get(raw, "address", "postalCode"),
                _deep_get(raw, "address", "zipcode"),
                realtor_address.get("postal_code"),
                raw.get("postalCode"),
            )
        ),
    }


def _extract_coordinates(raw: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    lat = _to_float(
        _first_non_empty(
            raw.get("latitude"),
            _deep_get(raw, "location", "lat"),
            _deep_get(raw, "location", "latitude"),
            _deep_get(raw, "coordinates", "lat"),
            _deep_get(raw, "Property", "Address", "Latitude"),
        )
    )
    lon = _to_float(
        _first_non_empty(
            raw.get("longitude"),
            _deep_get(raw, "location", "lng"),
            _deep_get(raw, "location", "longitude"),
            _deep_get(raw, "coordinates", "lng"),
            _deep_get(raw, "Property", "Address", "Longitude"),
        )
    )
    return lat, lon


def _synthesize_title(raw: Dict[str, Any], bedrooms: int, location: Dict[str, Optional[str]]) -> str:
    street = _clean_text(location.get("address_line_1"))
    city = _clean_text(location.get("city"))
    property_type = _clean_text(
        _first_non_empty(
            raw.get("propertyType"),
            _deep_get(raw, "Property", "Type"),
            _deep_get(raw, "Building", "Type"),
        )
    )
    if street:
        return street[:200]
    if property_type and city:
        return f"{bedrooms}BR {property_type} in {city}"[:200]
    return f"{bedrooms}BR listing in {city or 'target area'}"[:200]


def _resolve_host_user_id(explicit_user_id: Optional[str]) -> str:
    if explicit_user_id:
        return explicit_user_id

    sample = (
        supabase_admin.table("listings")
        .select("host_user_id")
        .limit(1000)
        .execute()
        .data
        or []
    )
    counts = Counter(row["host_user_id"] for row in sample if row.get("host_user_id"))
    if counts:
        return counts.most_common(1)[0][0]

    users = (
        supabase_admin.table("users")
        .select("id")
        .limit(1)
        .execute()
        .data
        or []
    )
    if users:
        return users[0]["id"]

    raise RuntimeError("Could not resolve a host_user_id. Pass --host-user-id explicitly.")


_FURNISHED_KEYWORDS = [
    "fully furnished", "fully-furnished", "comes furnished",
    "furnished unit", "furnished apartment", "furnished suite",
    "furnished condo", "furnished room", "furnished home",
    "furniture included", "all furniture", "furnished and",
    "is furnished", "are furnished",
]

_UNFURNISHED_KEYWORDS = [
    "unfurnished", "un-furnished", "not furnished",
]

def _description_says_furnished(description: Optional[str]) -> bool:
    if not description:
        return False
    text = description.lower()
    if any(kw in text for kw in _UNFURNISHED_KEYWORDS):
        return False
    return any(kw in text for kw in _FURNISHED_KEYWORDS)


def _prepare_listing(raw: Dict[str, Any], bucket: str, host_user_id: str) -> Optional[PreparedListing]:
    price = _extract_price(raw)
    bedrooms = _extract_bedrooms(raw)
    if not price or bedrooms is None:
        return None
    if bedrooms < 2 or bedrooms > 5:
        return None

    location = _extract_location(raw, bucket)
    title = _extract_title(raw) or _synthesize_title(raw, bedrooms, location)
    description = _extract_description(raw)
    if not description:
        return None
    lat, lon = _extract_coordinates(raw)
    bathrooms = _extract_bathrooms(raw)
    area = _extract_area(raw)
    amenities = _extract_amenities(raw)
    house_rules = _extract_house_rules(raw)
    images = _extract_images(raw)
    available_from = _clean_text(_first_non_empty(raw.get("availableFrom"), raw.get("available_from"))) or date.today().isoformat()

    listing = {
        "host_user_id": host_user_id,
        "status": "active",
        "title": title[:200],
        "description": description,
        "property_type": "entire_place",
        "lease_type": "fixed_term",
        "lease_duration_months": None,
        "number_of_bedrooms": bedrooms,
        "number_of_bathrooms": bathrooms,
        "area_sqft": area,
        "furnished": bool(
            amenities.get("furnished")
            or amenities.get("fully_furnished")
            or _description_says_furnished(description)
        ),
        "price_per_month": round(price, 2),
        "price_per_room": round(price / max(bedrooms, 1), 2),
        "utilities_included": bool(amenities.get("utilities_included") or amenities.get("all_utilities_included")),
        "deposit_amount": None,
        "address_line_1": location["address_line_1"],
        "city": location["city"],
        "state_province": location["state_province"],
        "postal_code": location["postal_code"],
        "country": location["country"],
        "latitude": lat,
        "longitude": lon,
        "available_from": available_from,
        "amenities": amenities or None,
        "house_rules": house_rules,
        "shared_spaces": None,
    }

    photos = [
        {"photo_url": url, "sort_order": index}
        for index, url in enumerate(images)
    ]
    return PreparedListing(listing=listing, photos=photos, bucket=bucket)


def _dedupe_key(item: PreparedListing) -> Tuple[Any, ...]:
    listing = item.listing
    return (
        listing.get("title", "").strip().lower(),
        listing.get("city", "").strip().lower(),
        listing.get("price_per_month"),
        listing.get("number_of_bedrooms"),
    )


def _load_existing_dedupe_keys() -> set[Tuple[Any, ...]]:
    seen: set[Tuple[Any, ...]] = set()
    page = 0
    page_size = 1000

    while True:
        rows = (
            supabase_admin.table("listings")
            .select("title,city,price_per_month,number_of_bedrooms")
            .range(page * page_size, page * page_size + page_size - 1)
            .execute()
            .data
            or []
        )
        if not rows:
            break

        for row in rows:
            seen.add(
                (
                    str(row.get("title", "")).strip().lower(),
                    str(row.get("city", "")).strip().lower(),
                    row.get("price_per_month"),
                    row.get("number_of_bedrooms"),
                )
            )

        if len(rows) < page_size:
            break
        page += 1

    return seen


def _wipe_existing() -> None:
    supabase_admin.table("stable_matches").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase_admin.table("listing_photos").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase_admin.table("listings").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()


def _is_transient_supabase_error(exc: Exception) -> bool:
    if not isinstance(exc, APIError):
        return False

    code = getattr(exc, "code", None)
    message = str(getattr(exc, "message", "") or exc)
    details = str(getattr(exc, "details", "") or "")
    haystack = f"{code} {message} {details}".lower()
    transient_markers = (" 500", " 502", " 503", " 504", "bad gateway", "gateway timeout", "cloudflare")
    return any(marker in haystack for marker in transient_markers)


def _execute_with_retry(request_builder: Any, *, attempts: int = 5, base_delay: float = 1.0) -> Any:
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return request_builder.execute()
        except Exception as exc:
            last_error = exc
            if not _is_transient_supabase_error(exc) or attempt == attempts:
                raise
            time.sleep(base_delay * attempt)
    raise last_error or RuntimeError("Supabase request failed without an exception")


def _insert_records(records: Iterable[PreparedListing]) -> Dict[str, int]:
    inserted = 0
    inserted_photos = 0

    for item in records:
        created = _execute_with_retry(supabase_admin.table("listings").insert(item.listing)).data
        if not created:
            continue
        listing_id = created[0]["id"]
        inserted += 1

        if item.photos:
            photo_rows = [{**photo, "listing_id": listing_id} for photo in item.photos]
            _execute_with_retry(supabase_admin.table("listing_photos").insert(photo_rows))
            inserted_photos += len(photo_rows)

    return {"listings": inserted, "photos": inserted_photos}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Padly listings from exported Apify datasets.")
    parser.add_argument("inputs", nargs="+", help="One or more exported JSON/JSONL dataset files.")
    parser.add_argument("--host-user-id", help="users.id to assign as the host for imported listings.")
    parser.add_argument("--limit-per-city", type=int, default=135, help="Max listings to keep per metro bucket.")
    parser.add_argument("--wipe-existing", action="store_true", help="Delete existing listings, listing_photos, and stable_matches before import.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarise without writing to Supabase.")
    args = parser.parse_args()

    host_user_id = _resolve_host_user_id(args.host_user_id)
    by_bucket: Dict[str, List[PreparedListing]] = defaultdict(list)
    seen = _load_existing_dedupe_keys()
    skipped_unknown_bucket = 0
    skipped_invalid = 0

    for input_path in [Path(value) for value in args.inputs]:
        for raw in _load_records(input_path):
            bucket = _infer_bucket(input_path, raw)
            if not bucket:
                skipped_unknown_bucket += 1
                continue

            prepared = _prepare_listing(raw, bucket=bucket, host_user_id=host_user_id)
            if prepared is None:
                skipped_invalid += 1
                continue

            key = _dedupe_key(prepared)
            if key in seen:
                continue
            if len(by_bucket[bucket]) >= args.limit_per_city:
                continue

            seen.add(key)
            by_bucket[bucket].append(prepared)

    ordered: List[PreparedListing] = []
    for bucket in ("toronto", "new_york", "san_francisco"):
        ordered.extend(by_bucket.get(bucket, []))

    summary = {
        "host_user_id": host_user_id,
        "prepared_total": len(ordered),
        "by_bucket": {bucket: len(rows) for bucket, rows in by_bucket.items()},
        "skipped_invalid": skipped_invalid,
        "skipped_unknown_bucket": skipped_unknown_bucket,
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))

    if args.dry_run:
        return 0

    if args.wipe_existing:
        _wipe_existing()

    inserted = _insert_records(ordered)
    print(json.dumps({"inserted": inserted, "host_user_id": host_user_id}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
