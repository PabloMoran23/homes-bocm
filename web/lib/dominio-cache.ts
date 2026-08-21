import { NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase/server";

export const DOMINIO_CACHE_HEADERS = {
  "Cache-Control": "public, s-maxage=900, stale-while-revalidate=86400",
};

export function dominioJson(data: unknown, cacheSeconds = 900) {
  return NextResponse.json(data, {
    headers: {
      "Cache-Control": `public, s-maxage=${cacheSeconds}, stale-while-revalidate=86400`,
    },
  });
}

export function dominioError(message: string, status = 500) {
  return NextResponse.json({ error: message }, { status });
}

export async function rpcDominio<T = unknown>(
  name: string,
  args: Record<string, unknown> = {},
): Promise<{ data: T | null; error: string | null; missing: boolean }> {
  const supabase = getSupabaseServer();
  if (!supabase) {
    return { data: null, error: "Supabase no configurado", missing: true };
  }
  const { data, error } = await supabase.rpc(name, args);
  if (error) {
    return { data: null, error: error.message, missing: false };
  }
  return { data: data as T, error: null, missing: false };
}
