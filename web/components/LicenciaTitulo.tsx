import { licenciaNotaDesdeTipo, licenciaTituloDesdeTipo } from "@/lib/ubicacion-resumen";

export function LicenciaTitulo({
  tipoExpediente,
  className = "font-medium text-slate-900",
  notaClassName = "mt-0.5 text-xs text-slate-500",
}: {
  tipoExpediente: string | null | undefined;
  className?: string;
  notaClassName?: string;
}) {
  const label = licenciaTituloDesdeTipo(tipoExpediente);
  const nota = licenciaNotaDesdeTipo(tipoExpediente);

  return (
    <>
      <p className={className}>{label}</p>
      {nota ? <p className={notaClassName}>{nota}</p> : null}
    </>
  );
}
