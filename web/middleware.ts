import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  getEdition,
  isDevOnlyRoute,
  isPublicApiRoute,
  isPublicRoute,
} from "@/lib/edition";

export function middleware(request: NextRequest) {
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
