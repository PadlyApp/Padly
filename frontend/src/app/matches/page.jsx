'use client';

import { ProtectedRoute } from '../components/ProtectedRoute';
import { useMatchesPage } from '../../features/matches/hooks/useMatchesPage';
import { MatchesPageView } from '../../features/matches/components/MatchesPageView';

function MatchesPageInner() {
  const vm = useMatchesPage();
  return <MatchesPageView {...vm} />;
}

export default function MatchesPage() {
  return (
    <ProtectedRoute>
      <MatchesPageInner />
    </ProtectedRoute>
  );
}
