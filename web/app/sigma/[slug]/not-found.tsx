import Link from "next/link";

export default function SigmaNotFound() {
  return (
    <main className="mx-auto max-w-lg px-4 py-16 text-center">
      <h1 className="text-xl font-semibold text-slate-900">Proyecto no encontrado</h1>
      <p className="mt-2 text-sm text-slate-600">
        No tenemos datos del ayuntamiento para esta referencia. Puede que el expediente no exista o
        que aún no lo hayamos sincronizado.
      </p>
      <Link
        href="/explore"
        className="mt-6 inline-block text-sm font-semibold text-[var(--portal-accent)] hover:underline"
      >
        ← Volver al mapa de Madrid
      </Link>
    </main>
  );
}
