"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useState } from "react";
import { editionLabel, isPublicEdition } from "@/lib/edition";

const navLinks = [
  { href: "/explore", label: "Explorar" },
  { href: "/madrid/estadisticas", label: "Estadísticas" },
  { href: "/boletin", label: "Tu zona" },
] as const;

function isNavActive(pathname: string, href: string) {
  if (pathname === href) return true;
  if (href === "/boletin" && pathname.startsWith("/boletin")) return true;
  if (
    href === "/explore" &&
    (pathname.startsWith("/explore") ||
      pathname.startsWith("/ubicacion") ||
      pathname.startsWith("/proyecto"))
  ) {
    return true;
  }
  if (
    href === "/madrid/estadisticas" &&
    (pathname.startsWith("/madrid/estadisticas") || pathname === "/estadisticas")
  ) {
    return true;
  }
  return false;
}

function linkClass(active: boolean, mobile = false) {
  const base = mobile
    ? "block rounded-lg px-4 py-3 text-base font-medium transition"
    : "rounded-md px-3 py-2 text-sm font-medium transition";
  return active
    ? `${base} bg-[var(--portal-accent-soft)] font-semibold text-[var(--portal-accent)]`
    : `${base} text-slate-700 hover:bg-slate-100 hover:text-slate-900`;
}

function MenuIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 22 22"
      fill="none"
      className="text-slate-800"
      aria-hidden
    >
      {open ? (
        <path
          d="M5 5l12 12M17 5L5 17"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
      ) : (
        <>
          <path d="M3 6h16M3 11h16M3 16h16" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}

export function NavBar() {
  const pathname = usePathname();
  const isPublic = isPublicEdition();
  const menuId = useId();
  const [open, setOpen] = useState(false);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    close();
  }, [pathname, close]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, close]);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/90 bg-white/95 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link
          href="/"
          onClick={close}
          className={`min-w-0 shrink-0 rounded-md px-2 py-1.5 text-sm font-semibold tracking-tight transition sm:text-base ${
            pathname === "/"
              ? "bg-[var(--portal-accent-soft)] text-[var(--portal-accent)]"
              : "text-slate-900 hover:bg-slate-100"
          }`}
        >
          <span className="text-[var(--portal-accent)]">Homes</span>
          <span className="text-slate-400"> · </span>
          <span className="hidden sm:inline">Urbanismo Madrid</span>
          <span className="sm:hidden">Madrid</span>
        </Link>

        <div className="flex items-center gap-2 md:gap-3">
          {isPublic ? (
            <span className="hidden shrink-0 rounded-md border border-teal-200/80 bg-teal-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-teal-800 sm:inline">
              Beta
            </span>
          ) : (
            <span className="hidden shrink-0 rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500 lg:inline">
              {editionLabel("full")}
            </span>
          )}

          <nav
            className="hidden items-center justify-center gap-1 md:flex"
            aria-label="Principal"
          >
            {navLinks.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={linkClass(isNavActive(pathname, href))}
              >
                {label}
              </Link>
            ))}
          </nav>

          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200/90 bg-white text-slate-800 shadow-sm transition hover:bg-slate-50 md:hidden"
            aria-expanded={open}
            aria-controls={menuId}
            aria-label={open ? "Cerrar menú" : "Abrir menú"}
            onClick={() => setOpen((v) => !v)}
          >
            <MenuIcon open={open} />
          </button>
        </div>
      </div>

      {open ? (
        <>
          <button
            type="button"
            aria-label="Cerrar menú"
            className="fixed inset-0 top-14 z-40 bg-slate-900/30 md:hidden"
            onClick={close}
          />
          <nav
            id={menuId}
            className="relative z-50 border-t border-slate-100 bg-white px-4 py-3 shadow-lg md:hidden"
            aria-label="Principal móvil"
          >
            <ul className="space-y-1">
              {navLinks.map(({ href, label }) => {
                const active = isNavActive(pathname, href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      onClick={close}
                      className={linkClass(active, true)}
                      aria-current={active ? "page" : undefined}
                    >
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
            {isPublic ? (
              <p className="mt-3 border-t border-slate-100 pt-3 text-center text-[10px] font-semibold uppercase tracking-wide text-teal-800">
                Versión beta · Madrid capital
              </p>
            ) : null}
          </nav>
        </>
      ) : null}
    </header>
  );
}
