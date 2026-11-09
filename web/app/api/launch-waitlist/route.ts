import { createClient } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return new NextResponse(null, { status: 403 });
  }
  if (!request.headers.get("content-type")?.startsWith("application/json") || Number(request.headers.get("content-length") || 0) > 2048) {
    return new NextResponse(null, { status: 413 });
  }

  let email: string;
  let source: "project" | "boletin" | "dashboard";
  let contextKey: string;
  try {
    const text = await request.text();
    if (text.length > 2048) return new NextResponse(null, { status: 413 });
    const body = JSON.parse(text);
    if (!body || typeof body !== "object") return new NextResponse(null, { status: 400 });
    if (body.website) return new NextResponse(null, { status: 204 });
    if (!["project", "boletin", "dashboard"].includes(body.source)) {
      return new NextResponse(null, { status: 400 });
    }
    source = body.source;
    contextKey = source === "project" && typeof body.contextKey === "string" ? body.contextKey.trim() : "";
    if ((source === "project" && !contextKey) || contextKey.length > 200) {
      return new NextResponse(null, { status: 400 });
    }
    email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
    if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return new NextResponse(null, { status: 400 });
    }
  } catch {
    return new NextResponse(null, { status: 400 });
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const registrationKey = process.env.LAUNCH_WAITLIST_KEY;
  if (!url || !key || !registrationKey) return new NextResponse(null, { status: 503 });
  const supabase = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { fetch: (input, init) => fetch(input, { ...init, signal: AbortSignal.timeout(5000) }) },
  });
  try {
    const { error } = await supabase.rpc("homes_launch_waitlist_register", {
      p_key: registrationKey,
      p_email: email,
      p_source: source,
      p_context_key: contextKey,
    });
    if (error) return new NextResponse(null, { status: 503 });
    return new NextResponse(null, { status: 204 });
  } catch {
    return new NextResponse(null, { status: 503 });
  }
}
