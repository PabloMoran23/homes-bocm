import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
/** RPC con SECURITY DEFINER: basta anon en servidor. Service role solo para sync/admin. */
const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export function getSupabaseServer() {
  if (!url || !key) {
    return null;
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

export function supabaseConfigured(): boolean {
  return Boolean(url && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}
