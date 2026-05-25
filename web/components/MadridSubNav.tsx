"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  {
    href: "/madrid/sigma",
    label: "Proyectos",
    description: "Planeamiento, gestión y urbanización (~4k)",
  },
  {
    href: "/madrid/bocm",
    label: "BOCM",
    description: "Anuncios parseados del boletín",
  },
  {
    href: "/madrid/licencias",
    label: "Licencias",
    description: "Obra otorgada (datos abiertos)",
  },
] as const;

export function MadridSubNav() {
  const pathname = usePathname();

  return (
    <nav className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-stretch">
      {tabs.map(({ href, label, description }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            className={`flex-1 rounded-xl border px-4 py-3 transition ${
              active
                ? "border-[var(--portal-accent)] bg-[var(--portal-accent-soft)]/60 shadow-sm ring-1 ring-[var(--portal-accent)]/30"
                : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
            }`}
          >
            <span
              className={`text-sm font-semibold ${
                active ? "text-[var(--portal-accent)]" : "text-slate-900"
              }`}
            >
              {label}
            </span>
            <span className="mt-0.5 block text-xs text-slate-500">{description}</span>
          </Link>
        );
      })}
    </nav>
  );
}
