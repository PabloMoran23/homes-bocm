"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const tabs = [
  { href: "/admin/municipios", label: "Municipios / bots" },
  { href: "/admin/pipeline", label: "Pipeline SIGMA" },
] as const;

export function AdminSubNav() {
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await fetch("/api/admin/auth", { method: "DELETE" });
    router.replace("/admin/login");
    router.refresh();
  }

  return (
    <nav className="mb-8 flex flex-wrap items-center gap-2 border-b border-slate-200 pb-4">
      <div className="mr-auto">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Interno</p>
        <h1 className="text-xl font-semibold text-slate-900">Operaciones</h1>
      </div>
      {tabs.map((tab) => {
        const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={
              active
                ? "rounded-lg bg-[var(--portal-accent-soft)] px-3 py-2 text-sm font-semibold text-[var(--portal-accent)]"
                : "rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }
          >
            {tab.label}
          </Link>
        );
      })}
      <button
        type="button"
        onClick={() => void logout()}
        className="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800"
      >
        Salir
      </button>
    </nav>
  );
}
