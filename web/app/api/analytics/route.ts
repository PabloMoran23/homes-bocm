import { createHmac } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";
import { getSupabaseServer } from "@/lib/supabase/server";
import { sanitizeAnalyticsBatch } from "@/lib/analytics-validation";
import { ADMIN_COOKIE, isValidAdminSession } from "@/lib/admin-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const key = process.env.ANALYTICS_RPC_KEY;
  if (process.env.NEXT_PUBLIC_SESSION_ANALYTICS !== "1" || !key) return new NextResponse(null, { status: 503 });
  if (request.headers.get("origin") !== request.nextUrl.origin) return new NextResponse(null, { status: 403 });
  if (/bot|crawler|spider|headless|lighthouse|prerender/i.test(request.headers.get("user-agent") || "")) return new NextResponse(null, { status: 204 });
  if (await isValidAdminSession(request.cookies.get(ADMIN_COOKIE)?.value)) return new NextResponse(null, { status: 204 });
  if (!request.headers.get("content-type")?.startsWith("application/json") || Number(request.headers.get("content-length") || 0) > 24000) return new NextResponse(null, { status: 413 });
  let events;
  try {
    const text = await request.text();
    if (text.length > 24000) return new NextResponse(null, { status: 413 });
    events = sanitizeAnalyticsBatch(JSON.parse(text));
  } catch { return new NextResponse(null, { status: 400 }); }
  if (!events) return new NextResponse(null, { status: 400 });
  const supabase = getSupabaseServer();
  if (!supabase) return new NextResponse(null, { status: 503 });
  // Short-lived rotating hash for rate limiting; raw IP is never stored.
  const ip = request.headers.get("x-vercel-forwarded-for") || request.headers.get("x-forwarded-for") || "local";
  const bucket = createHmac("sha256", key).update(`${Math.floor(Date.now() / 60000)}:${ip.split(",")[0]}`).digest("hex");
  const { data, error } = await supabase.rpc("homes_analytics_ingest", { p_key: key, p_bucket: bucket, p_events: events });
  if (error) { console.error("Analytics storage unavailable", error.code); return new NextResponse(null, { status: 503 }); }
  return new NextResponse(null, { status: data === false ? 429 : 204 });
}
