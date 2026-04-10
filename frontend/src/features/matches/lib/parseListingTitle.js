export function parseListingTitle(title) {
  if (!title) return { street: '', location: '' };
  const parts = title.split('|');
  if (parts.length >= 2) {
    return { street: parts[0].trim(), location: parts.slice(1).join(' ').trim() };
  }
  return { street: title.trim(), location: '' };
}
