import Link from "next/link";

export default function ProyectoNotFound() {
  return (
    <main className="mx-auto max-w-6xl flex-1 px-4 py-16 sm:px-6">
      <h1 className="text-2xl font-semibold text-slate-900">Proyecto no encontrado</h1>
      <p className="mt-2 text-slate-600">
        No existe en el dataset actual o el enlace es incorrecto. Regenera datos con{" "}
        <code className="rounded bg-slate-100 px-1 font-mono text-sm">npm run build-data</code> si
        acabas de parsear nuevos PDFs.
      </p>
      <Link
        href="/explore"
        className="mt-6 inline-flex text-sm font-semibold text-[var(--portal-accent)] hover:underline"
      >
        Volver al explorador
      </Link>
    </main>
  );
}
