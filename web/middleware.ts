import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  getEdition,
  isDevOnlyRoute,
  isPublicApiRoute,
  isPublicRoute,
} from "@/lib/edition";

function wwwRedirect(request: NextRequest): NextResponse | null {
  const host = request.headers.get("host") ?? "";
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "");
  if (!siteUrl) return null;

  let canonicalHost: string;
  try {
    canonicalHost = new URL(siteUrl).host;
  } catch {
    return null;
  }

  if (host !== `www.${canonicalHost}`) return null;

  const url = request.nextUrl.clone();
  url.host = canonicalHost;
  url.protocol = "https:";
  return NextResponse.redirect(url, 301);
}

export function middleware(request: NextRequest) {
  const www = wwwRedirect(request);
  if (www) return www;

  const edition = getEdition();
  if (edition === "full") return NextResponse.next();

  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/_next") || pathname.startsWith("/favicon")) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api")) {
    if (isPublicApiRoute(pathname)) return NextResponse.next();
    if (pathname.startsWith("/api/admin")) {
      return NextResponse.json({ error: "No disponible en esta versión" }, { status: 404 });
    }
    return NextResponse.next();
  }

  if (pathname === "/en-desarrollo") return NextResponse.next();

  if (isDevOnlyRoute(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/en-desarrollo";
    url.searchParams.set("from", pathname);
    return NextResponse.redirect(url);
  }

  if (isPublicRoute(pathname)) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/en-desarrollo";
  url.searchParams.set("from", pathname);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
