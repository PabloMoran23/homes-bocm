import Link from "next/link";

export default function UbicacionNotFound() {
  return (
    <main className="mx-auto max-w-lg flex-1 px-4 py-16 text-center sm:px-6">
      <h1 className="text-2xl font-semibold text-slate-900">Ubicación no encontrada</h1>
      <p className="mt-2 text-slate-600">
        No hay un inmueble con ese NDP en la base de datos local.
      </p>
      <Link
        href="/explore"
        className="mt-6 inline-block font-medium text-[var(--portal-accent)] hover:underline"
      >
        Volver al mapa
      </Link>
    </main>
  );
}
