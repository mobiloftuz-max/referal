import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://ugmzsvgkjjhcipbtfrbf.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase URL and Anon Key are missing. Check your .env file configurations.');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
