import { createClient } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { cleanFollowSegment, cleanFollowSignup } from "@/lib/seguir-proyecto";

export async function POST(request: NextRequest) {
  if (request.headers.get("origin") !== request.nextUrl.origin) {
    return new NextResponse(null, { status: 403 });
  }
  if (!request.headers.get("content-type")?.startsWith("application/json") || Number(request.headers.get("content-length") || 0) > 2048) {
    return new NextResponse(null, { status: 413 });
  }

  let signup: ReturnType<typeof cleanFollowSignup> = null;
  let segment: ReturnType<typeof cleanFollowSegment> = null;
  try {
    const text = await request.text();
    if (text.length > 2048) return new NextResponse(null, { status: 413 });
    const body = JSON.parse(text);
    if (!body || typeof body !== "object") return new NextResponse(null, { status: 400 });
    if (body.website) return new NextResponse(null, { status: 204 });
    if (body.intent === "segmento") segment = cleanFollowSegment(body);
    else signup = cleanFollowSignup(body);
    if (!segment && !signup) return new NextResponse(null, { status: 400 });
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
  const params = segment
    ? {
        p_key: registrationKey,
        p_email: segment.email,
        p_source: "project",
        p_context_key: segment.contextKey,
        p_segmento: segment.segmento,
      }
    : {
        p_key: registrationKey,
        p_email: signup!.email,
        p_source: signup!.source,
        p_context_key: signup!.contextKey,
        p_posicion: signup!.posicion,
        p_municipio: signup!.municipio,
        p_referrer: signup!.referrer,
        p_utm: signup!.utm,
        p_aviso: signup!.aviso,
        p_ambito: signup!.ambito,
      };
  try {
    const { error } = await supabase.rpc("homes_launch_waitlist_register", params);
    if (error) return new NextResponse(null, { status: 503 });
    return new NextResponse(null, { status: 204 });
  } catch {
    return new NextResponse(null, { status: 503 });
  }
}
