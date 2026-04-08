const TITLE_LOWER_WORDS = new Set(['a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'at', 'by', 'in', 'of', 'on', 'to', 'up']);

function toTitleCase(str) {
  if (!str) return '';
  return str.toLowerCase().split(' ').map((word, i) => {
    if (!word) return word;
    if (i > 0 && TITLE_LOWER_WORDS.has(word)) return word;
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(' ');
}

/**
 * Splits a raw listing title on the first `|` into a street address and a
 * location string.  Title-cases the street portion.
 *
 * e.g. "UPPER - 12 PERSICA STREET|Richmond Hill (Oak Ridges), Ontario L4E1L3"
 *   → { street: "Upper - 12 Persica Street", location: "Richmond Hill (Oak Ridges), Ontario L4E1L3" }
 */
export function parseListingTitle(raw) {
  if (!raw) return { street: '', location: '' };
  const pipeIdx = raw.indexOf('|');
  if (pipeIdx === -1) return { street: toTitleCase(raw.trim()), location: '' };
  return {
    street: toTitleCase(raw.slice(0, pipeIdx).trim()),
    location: raw.slice(pipeIdx + 1).trim(),
  };
}

const AMENITY_LABEL_OVERRIDES = {
  no_garage: 'No Garage',
  electric_vehicle_charge: 'EV Charging',
  all_utilities_included: 'All Utilities',
  laundry_options: 'Laundry',
  bike_storage: 'Bike Storage',
  bike_parking: 'Bike Storage',
  cats_allowed: 'Cats OK',
  dogs_allowed: 'Dogs OK',
  pets_allowed: 'Pets OK',
  smoking_allowed: 'Smoking OK',
  wheelchair_access: 'Wheelchair Access',
  utilities_included: 'Utilities Incl.',
  fully_furnished: 'Fully Furnished',
  comes_furnished: 'Furnished',
  single_family: 'House',
  single_family_home: 'House',
  hasairconditioning: 'Air Conditioning',
  hasfireplace: 'Fireplace',
  haspool: 'Pool',
  hasspa: 'Spa',
};

function isNumericToken(value) {
  return /^\d+$/.test(String(value || '').trim());
}

function normalizeAmenityToken(value) {
  if (value == null) return null;
  const raw = String(value).trim();
  if (!raw || isNumericToken(raw)) return null;
  return raw
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

/**
 * Returns normalized amenity keys that are actually active for a listing.
 * Handles object, array, and mixed payloads while filtering out numeric IDs.
 */
export function getActiveAmenityKeys(amenities) {
  if (!amenities || typeof amenities !== 'object') return [];

  const keys = [];
  const seen = new Set();

  const add = (candidate) => {
    const normalized = normalizeAmenityToken(candidate);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    keys.push(normalized);
  };

  if (Array.isArray(amenities)) {
    amenities.forEach((item) => {
      if (typeof item === 'string' || typeof item === 'number') {
        add(item);
      }
    });
    return keys;
  }

  Object.entries(amenities).forEach(([key, value]) => {
    if (!value) return;
    if (isNumericToken(key)) {
      if (typeof value === 'string' || typeof value === 'number') {
        add(value);
      }
      return;
    }
    add(key);
  });

  return keys;
}

/** Formats enum-like values (e.g., `for_rent`) for user-facing UI text. */
export function formatEnumLabel(value) {
  if (value == null) return '';
  return String(value)
    .trim()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Converts a snake_case amenity key into a human-readable label.
 * Uses a curated override map first; falls back to title-casing each word.
 */
export function formatAmenityLabel(key) {
  const normalized = normalizeAmenityToken(key);
  if (!normalized) return '';
  if (AMENITY_LABEL_OVERRIDES[normalized]) return AMENITY_LABEL_OVERRIDES[normalized];
  return normalized
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}
