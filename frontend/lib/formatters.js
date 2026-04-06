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
