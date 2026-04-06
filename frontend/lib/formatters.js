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
};

/**
 * Converts a snake_case amenity key into a human-readable label.
 * Uses a curated override map first; falls back to title-casing each word.
 */
export function formatAmenityLabel(key) {
  if (!key) return '';
  if (AMENITY_LABEL_OVERRIDES[key]) return AMENITY_LABEL_OVERRIDES[key];
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}
