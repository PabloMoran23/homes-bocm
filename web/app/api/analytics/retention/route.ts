import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase/server";
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  const expected = process.env.CRON_SECRET;
  const received = request.headers.get("authorization") || "";
  if (!expected || received.length !== `Bearer ${expected}`.length || !timingSafeEqual(Buffer.from(received), Buffer.from(`Bearer ${expected}`))) return new NextResponse(null, { status: 401 });
  const supabase = getSupabaseServer();
  if (!supabase || !process.env.ANALYTICS_RPC_KEY) return new NextResponse(null, { status: 503 });
  const { error } = await supabase.rpc("homes_analytics_cleanup", { p_key: process.env.ANALYTICS_RPC_KEY });
  return NextResponse.json({ ok: !error }, { status: error ? 503 : 200 });
}
