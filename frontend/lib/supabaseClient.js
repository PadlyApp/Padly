import { createClient } from '@supabase/supabase-js';

// Empty URL throws in createClient; prerender still loads this via Navigation → authService.
// Defaults match frontend CI when env is unset.
const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() ||
  'https://example.supabase.co';
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() || 'dummy-anon-key';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

