'use client';

import { ProtectedRoute } from '../../components/ProtectedRoute';
import { useGroupDetailPage } from '../../../features/groups/detail/hooks/useGroupDetailPage';
import { GroupDetailPageView } from '../../../features/groups/detail/components/GroupDetailPageView';

function GroupDetailPageInner() {
  const vm = useGroupDetailPage();
  return <GroupDetailPageView {...vm} />;
}

export default function GroupDetailPage() {
  return (
    <ProtectedRoute>
      <GroupDetailPageInner />
    </ProtectedRoute>
  );
}
