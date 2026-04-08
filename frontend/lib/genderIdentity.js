export const GENDER_IDENTITY_OPTIONS = [
  { value: 'woman', label: 'Woman' },
  { value: 'man', label: 'Man' },
  { value: 'other', label: 'Other' },
  { value: 'prefer_not_to_say', label: 'Prefer not to say' },
];

const ALLOWED_GENDER_IDENTITIES = new Set(
  GENDER_IDENTITY_OPTIONS.map((option) => option.value)
);

export function normalizeGenderIdentity(value) {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');

  if (!normalized) return null;
  return ALLOWED_GENDER_IDENTITIES.has(normalized) ? normalized : null;
}
