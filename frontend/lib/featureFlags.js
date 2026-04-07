/**
 * Roommates/groups entry points in the UI. When false, matches hidden /groups behavior.
 * Set `NEXT_PUBLIC_ENABLE_GROUPS=true` when you remove group redirects in `next.config.js`.
 */
export const GROUPS_FEATURE_ENABLED =
  process.env.NEXT_PUBLIC_ENABLE_GROUPS === 'true';
