'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Center, Loader, Text, Stack, Alert } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { supabase } from '../../../../lib/supabaseClient';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const AUTH_STORAGE_KEY = 'padly_auth';
const USER_STORAGE_KEY = 'padly_user';

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Supabase uses PKCE flow by default: after OAuth it redirects back with
        // ?code=... in the URL. exchangeCodeForSession exchanges it for real tokens.
        // Fall back to getSession() for the older implicit (hash fragment) flow.
        const params = new URLSearchParams(window.location.search);
        const code = params.get('code');

        let session;
        if (code) {
          const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) throw exchangeError;
          session = data?.session;
        } else {
          const { data, error: sessionError } = await supabase.auth.getSession();
          if (sessionError) throw sessionError;
          session = data?.session;
        }

        if (!session) {
          throw new Error('No session returned from Google sign-in. Please try again.');
        }

        const { access_token, refresh_token, expires_in } = session;

        // Persist tokens in the same shape AuthContext expects
        const expiresAt = Date.now() + expires_in * 1000;
        const authState = { accessToken: access_token, refreshToken: refresh_token, expiresAt };
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authState));

        // Fetch / upsert the user profile from FastAPI.
        // /me auto-creates public.users + solo group for brand-new Google users.
        const meResponse = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${access_token}` },
        });

        const meRaw = await meResponse.text();
        let meData;
        try {
          meData = meRaw ? JSON.parse(meRaw) : null;
        } catch {
          meData = null;
        }

        if (!meResponse.ok) {
          const detail = meData?.detail;
          let message = 'Failed to load your profile. Please try again.';
          if (typeof detail === 'string') message = detail;
          else if (Array.isArray(detail) && detail.length > 0) {
            message = detail
              .map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d)))
              .join(' ');
          }
          throw new Error(message);
        }
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(meData.user));

        // Use server-side truth (has_preferences) to decide where to send the user.
        // localStorage 'padly_preferences_complete' is unreliable: it may be missing
        // for new users or stale from a previous browser session.
        // Also use a full-page navigation (not router.replace) so AuthContext
        // re-initializes from localStorage and picks up the newly saved tokens.
        const hasPreferences = meData.user?.has_preferences;
        window.location.href = hasPreferences ? '/discover' : '/preferences-setup';
      } catch (err) {
        console.error('OAuth callback error:', err);
        setError(err?.message || 'Something went wrong during sign-in. Please try again.');
      }
    };

    handleCallback();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <Center h="100vh">
        <Stack align="center" gap="md" maw={400} px="md">
          <Alert
            icon={<IconAlertCircle size={18} />}
            color="red"
            title="Sign-in failed"
            w="100%"
          >
            {error}
          </Alert>
          <Text
            component="a"
            href="/login"
            size="sm"
            c="blue"
            style={{ cursor: 'pointer', textDecoration: 'underline' }}
          >
            Back to login
          </Text>
        </Stack>
      </Center>
    );
  }

  return (
    <Center h="100vh">
      <Stack align="center" gap="md">
        <Loader size="md" />
        <Text size="sm" c="dimmed">Signing you in…</Text>
      </Stack>
    </Center>
  );
}
