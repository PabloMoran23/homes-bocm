import { normalizarActuacionEdificio, type ActuacionEdificioInput } from "@/lib/actuacion-edificio";
import { licenciaNotaDesdeTipo } from "@/lib/ubicacion-resumen";

export function LicenciaTitulo({
  tipoExpediente,
  objeto,
  uso,
  procedimiento,
  licencia,
  className = "font-medium text-slate-900",
  notaClassName = "mt-0.5 text-xs text-slate-500",
}: {
  tipoExpediente?: string | null;
  objeto?: string | null;
  uso?: string | null;
  procedimiento?: string | null;
  licencia?: ActuacionEdificioInput | null;
  className?: string;
  notaClassName?: string;
}) {
  const input: ActuacionEdificioInput =
    licencia ?? {
      tipo_expediente: tipoExpediente,
      objeto,
      uso,
      procedimiento,
    };
  const norm = normalizarActuacionEdificio(input);
  const label = norm.etiqueta;
  const nota = licenciaNotaDesdeTipo(input.tipo_expediente);

  return (
    <>
      <p className={className}>{label}</p>
      {nota ? <p className={notaClassName}>{nota}</p> : null}
    </>
  );
}
