import { NextResponse } from "next/server";
import { projectFromDominioRow } from "@/lib/proyecto-dominio-map";
import type { Project } from "@/lib/types";
import { getSupabaseServer } from "@/lib/supabase/server";

export const revalidate = 3600;

type RpcPayload = {
  generatedAt?: string;
  projects?: Record<string, unknown>[];
};

export async function GET() {
  const supabase = getSupabaseServer();
  if (!supabase) {
    return NextResponse.json({ error: "Supabase no configurado" }, { status: 503 });
  }

  const { data, error } = await supabase.rpc("list_proyectos_bocm_madrid");
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const payload = (data ?? {}) as RpcPayload;
  const projects: Project[] = (payload.projects ?? []).map((row) =>
    projectFromDominioRow(row),
  );

  return NextResponse.json(
    { generatedAt: payload.generatedAt ?? null, projects },
    { headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" } },
  );
}
