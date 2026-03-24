import { redirect } from 'next/navigation';

export default function PreferencesPage() {
  redirect('/account?tab=preferences');
}
