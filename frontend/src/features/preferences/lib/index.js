// ── Constants ─────────────────────────────────────────────────────────────────

export const NUM_HISTOGRAM_BINS = 30;

export const PREFERENCE_PAYLOAD_KEYS = [
  'target_country',
  'target_state_province',
  'target_city',
  'required_bedrooms',
  'target_bathrooms',
  'target_deposit_amount',
  'furnished_preference',
  'gender_policy',
  'move_in_date',
  'target_lease_type',
  'target_lease_duration_months',
  'lifestyle_preferences',
];

// ── Select option arrays ──────────────────────────────────────────────────────

export const LEASE_TYPE_OPTIONS = [
  { value: 'fixed', label: 'Fixed-term lease' },
  { value: 'month_to_month', label: 'Month-to-month' },
  { value: 'sublet', label: 'Sublet' },
  { value: 'any', label: 'Any' },
];

export const FURNISHED_PREF_OPTIONS = [
  { value: 'required', label: 'Must be furnished' },
  { value: 'preferred', label: 'Prefer furnished' },
  { value: 'no_preference', label: 'No preference' },
];

export const GENDER_POLICY_OPTIONS = [
  { value: 'mixed_ok', label: 'Mixed gender is okay' },
  { value: 'same_gender_only', label: 'Same gender only' },
];

// ── Payload helpers ───────────────────────────────────────────────────────────

/** Picks only the recognised preference keys from a source object. */
export function pickPreferenceFields(source) {
  const out = {};
  for (const key of PREFERENCE_PAYLOAD_KEYS) {
    if (Object.prototype.hasOwnProperty.call(source || {}, key)) {
      out[key] = source[key];
    }
  }
  return out;
}

// ── Normalisation helpers ─────────────────────────────────────────────────────

export function normalizeNumericInput(value) {
  if (value === '' || value == null) return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function normalizeIntInput(value) {
  const parsed = normalizeNumericInput(value);
  if (parsed == null) return null;
  return Math.trunc(parsed);
}

export function normalizeBathroomsPreference(value) {
  const parsed = normalizeNumericInput(value);
  if (parsed == null) return null;
  return parsed < 1 ? 1 : Math.round(parsed);
}

// ── Select option helpers ─────────────────────────────────────────────────────

function normalizeOptionText(value) {
  return String(value || '').trim().toLowerCase();
}

/**
 * Looks for an option whose value or label case-insensitively matches
 * `selectedValue`. Returns the option object or null.
 */
export function findMatchingOption(options, selectedValue) {
  if (!selectedValue) return null;
  const selectedNorm = normalizeOptionText(selectedValue);
  return (
    options.find((opt) => {
      const valueNorm = normalizeOptionText(opt?.value);
      const labelNorm = normalizeOptionText(opt?.label);
      return selectedNorm === valueNorm || selectedNorm === labelNorm;
    }) || null
  );
}

/**
 * Returns `options` with `selectedValue` injected at the front when it is not
 * already present. This keeps the currently-selected item visible in a Select
 * even before the full option list is loaded.
 */
export function withSelectedOption(options, selectedValue) {
  if (!selectedValue) return options;
  const exists = options.some((opt) => (opt?.value ?? null) === selectedValue);
  if (exists) return options;
  return [{ value: selectedValue, label: selectedValue }, ...options];
}

// ── Price helpers ─────────────────────────────────────────────────────────────

export function formatPrice(val) {
  return `$${Math.round(val).toLocaleString()}`;
}

/**
 * Approximates the number of listings whose price midpoint falls within
 * [lo, hi], using proportional overlap for partial bins.
 */
export function calcListingsInRange(bins, priceRange) {
  if (!bins || !bins.length) return 0;
  const [lo, hi] = priceRange;
  return bins.reduce((sum, bin) => {
    if (bin.range_max <= lo || bin.range_min >= hi) return sum;
    if (bin.range_min >= lo && bin.range_max <= hi) return sum + bin.count;
    const overlap = Math.min(bin.range_max, hi) - Math.max(bin.range_min, lo);
    const width = bin.range_max - bin.range_min;
    return sum + Math.round(bin.count * (overlap / width));
  }, 0);
}
