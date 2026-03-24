import { redirect } from 'next/navigation';

export default function InvitationsPage() {
  redirect('/groups?tab=invitations');
}
