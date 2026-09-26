"use client";

import { usePathname } from "next/navigation";
import { SiteLogo } from "@/components/SiteLogo";
import { isPublicEdition } from "@/lib/edition";
import { SITE_CONTACT_EMAIL, siteContactMailto } from "@/lib/site-contact";

const FULL_BLEED_PREFIXES = ["/explore", "/boletin"];

function ContactLine({ compact }: { compact?: boolean }) {
  return (
    <p
      className={
        compact
          ? "text-center text-xs leading-relaxed text-slate-500"
          : "text-sm leading-relaxed text-slate-600"
      }
    >
      Si necesitas más información o atención personalizada, escríbenos a{" "}
      <a
        href={siteContactMailto()}
        className="font-medium text-[var(--portal-accent)] hover:underline"
      >
        {SITE_CONTACT_EMAIL}
      </a>
      .
    </p>
  );
}

export function SiteFooter() {
  const pathname = usePathname();
  const compact = FULL_BLEED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
  const isPublic = isPublicEdition();

  if (compact) {
    return (
      <footer className="shrink-0 border-t border-[var(--portal-paper-deep)] bg-[var(--portal-paper)]/95 px-4 py-2.5 backdrop-blur-sm">
        <ContactLine compact />
      </footer>
    );
  }

  return (
    <footer className="mt-auto border-t border-[var(--portal-paper-deep)] bg-[var(--portal-paper-deep)]/70 py-8 text-sm text-[var(--portal-ink)]/70">
      <div className="mx-auto max-w-6xl space-y-4 px-4 sm:px-6">
        <p className="leading-relaxed">
          <span className="mb-2 inline-flex items-center gap-2">
            <SiteLogo height={20} className="opacity-80" />
            <strong className="font-semibold text-slate-800">Homes · Urbanismo</strong>
          </span>{" "}
          {isPublic
            ? "te acerca la actividad urbanística de Madrid capital: obras, planes y anuncios oficiales, en mapa y fichas claras."
            : "te acerca lo que importa alrededor de tu zona: seguimiento de actuaciones, lectura clara y herramientas para comparar y reaccionar a tiempo."}
        </p>
        <ContactLine />
      </div>
    </footer>
  );
}
