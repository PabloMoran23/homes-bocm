import { NextResponse } from "next/server";
import type { MadridSigmaDataset } from "@/lib/types";
import { getSupabaseServer } from "@/lib/supabase/server";

export const revalidate = 3600;

export async function GET() {
  const supabase = getSupabaseServer();
  if (!supabase) {
    return NextResponse.json(
      { error: "Supabase no configurado" },
      { status: 503 },
    );
  }

  const { data, error } = await supabase.rpc("list_proyectos_madrid", {
    p_limit: 8000,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data as MadridSigmaDataset, {
    headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" },
  });
}
