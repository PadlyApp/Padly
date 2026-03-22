const LIKED_KEY = 'padly_liked_listings';

export function getLikedListings() {
  if (typeof window === 'undefined') return [];
  try { return JSON.parse(localStorage.getItem(LIKED_KEY) || '[]'); }
  catch { return []; }
}

export function saveLikedListing(listing) {
  const existing = getLikedListings();
  if (existing.find((l) => l.listing_id === listing.listing_id)) return;
  localStorage.setItem(LIKED_KEY, JSON.stringify([...existing, listing]));
}

export function clearLikedListings() {
  localStorage.removeItem(LIKED_KEY);
}
