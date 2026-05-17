import Link from "next/link";
import type { ReactNode } from "react";

export function DetailPageShell({
  breadcrumb,
  hero,
  aside,
  children,
  footer,
}: {
  breadcrumb: ReactNode;
  hero: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <main className="mx-auto max-w-[90rem] flex-1 px-4 py-6 sm:px-6 sm:py-8">
      <nav className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-500">{breadcrumb}</nav>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] lg:items-start xl:gap-8">
        <div className="min-w-0 space-y-6">
          {hero}
          {children}
        </div>
        {aside ? (
          <aside className="min-w-0 space-y-4 lg:sticky lg:top-[4.25rem] lg:self-start">{aside}</aside>
        ) : null}
      </div>

      {footer ? <div className="mt-8 border-t border-slate-200 pt-6">{footer}</div> : null}
    </main>
  );
}

export function DetailBreadcrumbLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="font-medium text-[var(--portal-accent)] hover:underline">
      {children}
    </Link>
  );
}
