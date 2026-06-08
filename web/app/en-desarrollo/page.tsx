import type { Metadata } from "next";
import Link from "next/link";
import { getEdition } from "@/lib/edition";

export const metadata: Metadata = {
  title: "En desarrollo",
  robots: { index: false, follow: false },
};

const PUBLIC_LINKS = [
  { href: "/explore", label: "Explorar Madrid" },
  { href: "/boletin", label: "Boletín de tu zona" },
  { href: "/madrid/estadisticas", label: "Estadísticas" },
  { href: "/", label: "Inicio" },
] as const;

export default async function EnDesarrolloPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string }>;
}) {
  const { from } = await searchParams;
  const edition = getEdition();

  return (
    <main className="mx-auto flex max-w-lg flex-1 flex-col justify-center px-4 py-16 sm:px-6">
      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--portal-warm)]">
        Próximamente
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
        Esta sección aún está en desarrollo
      </h1>
      <p className="mt-4 text-sm leading-relaxed text-slate-600">
        La versión publicada de Homes incluye el mapa unificado, el boletín por dirección, las fichas
        de detalle y el panel de estadísticas. Estamos preparando más herramientas para una próxima
        actualización.
      </p>
      {from ? (
        <p className="mt-3 font-mono text-xs text-slate-500">
          Ruta solicitada: <span className="text-slate-700">{from}</span>
        </p>
      ) : null}
      {edition === "full" ? (
        <p className="mt-3 rounded-lg border border-amber-200/80 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Estás en edición <strong>full</strong> (desarrollo). Si ves esta página, la ruta no está
          implementada o el middleware la está bloqueando por error.
        </p>
      ) : null}
      <ul className="mt-8 flex flex-col gap-2">
        {PUBLIC_LINKS.map(({ href, label }) => (
          <li key={href}>
            <Link
              href={href}
              className="inline-flex items-center text-sm font-semibold text-[var(--portal-accent)] hover:underline"
            >
              {label} →
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
