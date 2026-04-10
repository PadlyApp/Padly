'use client';

import { useDiscoverPage } from '../../features/discover/hooks/useDiscoverPage';
import { DiscoverPageView } from '../../features/discover/components/DiscoverPageView';

export default function DiscoverPage() {
  // /discover is intentionally public — guests can browse without logging in.
  // Rate limiting and result capping for unauthenticated requests are enforced server-side.
  const discover = useDiscoverPage();
  return <DiscoverPageView {...discover} />;
}
