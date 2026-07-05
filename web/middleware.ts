import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  getEdition,
  isDevOnlyRoute,
  isPublicApiRoute,
  isPublicRoute,
} from "@/lib/edition";
import {
  ADMIN_COOKIE,
  isAdminPath,
  isAdminPublicPath,
  isValidAdminSession,
} from "@/lib/admin-auth";

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

function isMetadataRoute(pathname: string): boolean {
  const base = pathname.split("?")[0];
  return (
    base === "/opengraph-image" ||
    base === "/twitter-image" ||
    base === "/sitemap.xml" ||
    base === "/robots.txt" ||
    base === "/manifest.webmanifest"
  );
}

async function adminGate(request: NextRequest): Promise<NextResponse | null> {
  const { pathname } = request.nextUrl;
  if (!isAdminPath(pathname)) return null;

  const edition = getEdition();
  if (edition === "public") {
    if (pathname.startsWith("/api/admin")) {
      return NextResponse.json({ error: "No disponible" }, { status: 404 });
    }
    const url = request.nextUrl.clone();
    url.pathname = "/en-desarrollo";
    url.searchParams.set("from", pathname);
    return NextResponse.redirect(url);
  }

  if (isAdminPublicPath(pathname)) return NextResponse.next();

  const ok = await isValidAdminSession(request.cookies.get(ADMIN_COOKIE)?.value);
  if (ok) return NextResponse.next();

  if (pathname.startsWith("/api/admin")) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const login = request.nextUrl.clone();
  login.pathname = "/admin/login";
  login.searchParams.set("from", pathname);
  return NextResponse.redirect(login);
}

export async function middleware(request: NextRequest) {
  const www = wwwRedirect(request);
  if (www) return www;

  const { pathname } = request.nextUrl;

  if (isMetadataRoute(pathname)) return NextResponse.next();

  const admin = await adminGate(request);
  if (admin) return admin;

  const edition = getEdition();
  if (edition === "full") return NextResponse.next();

  if (pathname.startsWith("/_next") || pathname.startsWith("/favicon")) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api")) {
    if (isPublicApiRoute(pathname)) return NextResponse.next();
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
