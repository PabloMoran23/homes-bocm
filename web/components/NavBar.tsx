"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { editionLabel, isPublicEdition } from "@/lib/edition";

const navLinks = [
  { href: "/explore", label: "Explorar" },
  { href: "/madrid/estadisticas", label: "Estadísticas" },
  { href: "/boletin", label: "Tu zona" },
] as const;

export function NavBar() {
  const pathname = usePathname();
  const isPublic = isPublicEdition();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/90 bg-white/95 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 sm:gap-4 sm:px-6">
        <Link
          href="/"
          className={`shrink-0 rounded-md px-2 py-1.5 text-sm font-semibold tracking-tight transition sm:text-base ${
            pathname === "/"
              ? "bg-[var(--portal-accent-soft)] text-[var(--portal-accent)]"
              : "text-slate-900 hover:bg-slate-100"
          }`}
        >
          <span className="text-[var(--portal-accent)]">Homes</span>
          <span className="text-slate-400"> · </span>
          <span className="hidden sm:inline">Urbanismo Madrid</span>
        </Link>
        <nav className="flex min-w-0 flex-1 items-center justify-end gap-0.5 overflow-x-auto text-sm font-medium sm:justify-center sm:gap-1">
          {navLinks.map(({ href, label }) => {
            const active =
              pathname === href ||
              (href === "/boletin" && pathname.startsWith("/boletin")) ||
              (href === "/explore" &&
                (pathname.startsWith("/explore") ||
                  pathname.startsWith("/ubicacion") ||
                  pathname.startsWith("/proyecto"))) ||
              (href === "/madrid/estadisticas" &&
                (pathname.startsWith("/madrid/estadisticas") ||
                  pathname === "/estadisticas"));
            return (
              <Link
                key={href}
                href={href}
                className={`shrink-0 rounded-md px-2.5 py-2 transition sm:px-3 ${
                  active
                    ? "bg-[var(--portal-accent-soft)] font-semibold text-[var(--portal-accent)]"
                    : "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        {!isPublic ? (
          <span className="hidden shrink-0 rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500 lg:inline">
            {editionLabel("full")}
          </span>
        ) : (
          <span className="hidden shrink-0 rounded-md border border-teal-200/80 bg-teal-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-teal-800 lg:inline">
            Beta
          </span>
        )}
      </div>
    </header>
  );
}
