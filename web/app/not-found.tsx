import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Página no encontrada",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-lg flex-1 flex-col justify-center px-4 py-16 sm:px-6">
      <p className="text-xs font-semibold uppercase tracking-wider text-[var(--portal-warm)]">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
        No encontramos esta página
      </h1>
      <p className="mt-4 text-sm leading-relaxed text-slate-600">
        La ruta no existe o ya no está disponible. Puedes volver al mapa, al boletín por dirección o al
        panel de estadísticas.
      </p>
      <ul className="mt-8 flex flex-col gap-2">
        <li>
          <Link
            href="/explore"
            className="text-sm font-semibold text-[var(--portal-accent)] hover:underline"
          >
            Explorar Madrid →
          </Link>
        </li>
        <li>
          <Link
            href="/boletin"
            className="text-sm font-semibold text-[var(--portal-accent)] hover:underline"
          >
            Boletín de tu zona →
          </Link>
        </li>
        <li>
          <Link href="/" className="text-sm font-semibold text-[var(--portal-accent)] hover:underline">
            Inicio →
          </Link>
        </li>
      </ul>
    </div>
  );
}
