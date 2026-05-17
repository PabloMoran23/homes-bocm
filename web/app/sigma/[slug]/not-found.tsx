import Link from "next/link";

export default function SigmaNotFound() {
  return (
    <main className="mx-auto max-w-lg px-4 py-16 text-center">
      <h1 className="text-xl font-semibold text-slate-900">Expediente no encontrado</h1>
      <p className="mt-2 text-sm text-slate-600">
        No hay datos en el catálogo SIGMA ni en el visor para este identificador.
      </p>
      <Link
        href="/madrid/sigma"
        className="mt-6 inline-block text-sm font-semibold text-[var(--portal-accent)] hover:underline"
      >
        ← Volver al mapa SIGMA
      </Link>
    </main>
  );
}
