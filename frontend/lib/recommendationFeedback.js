export const MATCHES_FEEDBACK_CHOICES = [
  { value: 'not_useful', label: 'Not useful' },
  { value: 'somewhat_useful', label: 'Somewhat useful' },
  { value: 'very_useful', label: 'Very useful' },
];

export const MATCHES_NEGATIVE_REASON_CHOICES = [
  { value: 'too_expensive', label: 'Too expensive' },
  { value: 'wrong_location', label: 'Wrong location' },
  { value: 'not_my_style', label: 'Not my style' },
  { value: 'too_few_good_options', label: 'Too few good options' },
  { value: 'other', label: 'Other' },
];

export function createRecommendationClientSessionId(surface = 'matches') {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${surface}-${crypto.randomUUID()}`;
  }

  return `${surface}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
