import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
/** RPC con SECURITY DEFINER: basta anon en servidor. Service role solo para sync/admin. */
const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/**
 * Build and request budget for a Supabase round-trip.
 * `next build` prerenders the homepage and every dominio route with `revalidate`.
 * Those calls use this client. A saturated database accepts the TCP connection and
 * never answers, and static generation fails after 60s. Returning a 504 (not an
 * AbortError) keeps postgrest from retrying or throwing, so callers can fall back.
 */
const SUPABASE_FETCH_TIMEOUT_MS = 4_000;

function supabaseFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const timeout = AbortSignal.timeout(SUPABASE_FETCH_TIMEOUT_MS);
  const signal = init?.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
  return fetch(input, { ...init, signal }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : "network error";
    return Response.json(
      {
        message: `Supabase no respondió (${detail})`,
        code: "supabase_unreachable",
        details: null,
        hint: null,
      },
      { status: 504 },
    );
  });
}

export function getSupabaseServer() {
  if (!url || !key) {
    return null;
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { fetch: supabaseFetch },
  });
}

export function supabaseConfigured(): boolean {
  return Boolean(url && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}
