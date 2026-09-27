"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SiteLogo } from "@/components/SiteLogo";
import { isPublicEdition } from "@/lib/edition";
import { SITE_CONTACT_EMAIL, siteContactMailto } from "@/lib/site-contact";
import { DASHBOARD } from "@/lib/ui-labels";

const FULL_BLEED_PREFIXES = ["/explore", "/boletin"];

const FOOTER_LINKS = [
  { href: "/explore", label: "Explorar" },
  { href: "/madrid/estadisticas", label: DASHBOARD },
  { href: "/boletin", label: "Tu zona" },
] as const;

function ContactLine({ compact }: { compact?: boolean }) {
  return (
    <p className={compact ? "text-center text-xs text-white/70" : "text-sm leading-relaxed text-white/70"}>
      {compact ? (
        <a href={siteContactMailto()} className="font-medium text-white hover:underline">
          {SITE_CONTACT_EMAIL}
        </a>
      ) : (
        <>
          Una calle, un distrito o una ciudad.{" "}
          <a href={siteContactMailto()} className="font-medium text-white hover:underline">
            {SITE_CONTACT_EMAIL}
          </a>
        </>
      )}
    </p>
  );
}

export function SiteFooter() {
  const pathname = usePathname();
  const compact = FULL_BLEED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  const isPublic = isPublicEdition();

  if (compact) {
    return (
      <footer className="shrink-0 bg-[var(--portal-ink)] px-4 py-2.5 text-[var(--portal-paper)]">
        <ContactLine compact />
      </footer>
    );
  }

  return (
    <footer className="mt-auto bg-[var(--portal-ink)] text-[var(--portal-paper)]">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[minmax(0,1.4fr)_auto_auto] md:items-start md:gap-16">
        <div>
          <Link href="/" className="inline-flex items-center gap-2.5">
            <SiteLogo height={28} className="brightness-0 invert" />
            <span className="text-base font-semibold tracking-tight">
              <span className="text-white">Homes</span>
              <span className="text-white/35"> · </span>
              Urbanismo
            </span>
          </Link>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/70">
            {isPublic
              ? "Obra, planes y el panorama de Madrid ciudad, y el planeamiento que se publica en España."
              : "Obra, planes y lectura clara de lo que se mueve alrededor de tu zona."}
          </p>
        </div>

        <nav aria-label="Pie">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/45">Recorrer</p>
          <ul className="mt-3 space-y-2">
            {FOOTER_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="text-sm text-white/85 transition hover:text-white">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/45">Escribirnos</p>
          <a
            href={siteContactMailto()}
            className="mt-3 block text-sm font-medium text-white hover:underline"
          >
            {SITE_CONTACT_EMAIL}
          </a>
          <p className="mt-2 max-w-[16rem] text-sm leading-relaxed text-white/60">
            Una calle, un distrito o una ciudad.
          </p>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-white/45 sm:px-6">
          <span>Madrid ciudad</span>
          <span>España</span>
        </div>
      </div>
    </footer>
  );
}
