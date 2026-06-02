import { NextResponse } from "next/server";
import type { MadridSigmaClasificacionFile } from "@/lib/sigma-classification-filters";
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

  const { data, error } = await supabase.rpc("list_sigma_clasificacion");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const byExpediente = (data ?? {}) as MadridSigmaClasificacionFile["byExpediente"];
  const body: MadridSigmaClasificacionFile = {
    generatedAt: new Date().toISOString(),
    byExpediente: byExpediente ?? {},
  };

  return NextResponse.json(body, {
    headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" },
  });
}
