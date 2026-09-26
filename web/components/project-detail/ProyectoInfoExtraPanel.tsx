import { TramitacionTimeline } from "@/components/project-detail/TramitacionTimeline";
import {
  PROYECTO_INFO_BLOQUE_LABEL,
  type ProyectoInfoBloque,
  type ProyectoInfoDato,
  type ProyectoInfoExtra,
  type ProyectoInfoHallazgo,
} from "@/lib/proyecto-info-extra";
import type { SigmaVisorTramite } from "@/lib/types";

const CONFIANZA_LABEL = { alta: "Alta", media: "Media", baja: "Baja" } as const;
const FUENTE_LABEL = { oficial: "Oficial", prensa: "Prensa", web: "Web" } as const;

const DATOS_COLUMNAS: ProyectoInfoBloque[][] = [
  ["situacion", "programa"],
  ["cifras", "actores"],
];

export type ProyectoInfoTabId = "relato" | "datos" | "cronologia" | "prensa";

function formatDay(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric" });
}

export function proyectoInfoTabs(info: ProyectoInfoExtra): { id: ProyectoInfoTabId; label: string }[] {
  const tabs: { id: ProyectoInfoTabId; label: string }[] = [
    { id: "relato", label: "Qué está pasando" },
    { id: "datos", label: "Datos" },
  ];
  if (info.datos.some((dato) => dato.bloque === "cronologia")) {
    tabs.push({ id: "cronologia", label: "Cronología" });
  }
  if (info.datos.some((dato) => dato.bloque === "prensa") || info.hallazgos.length > 0) {
    tabs.push({ id: "prensa", label: "Prensa" });
  }
  return tabs;
}

export function proyectoNombrePopular(info: ProyectoInfoExtra): string | null {
  const row = info.datos.find((dato) => dato.clave === "nombre_publico" && dato.valor.trim());
  return row?.valor.trim() ?? null;
}

function formatChipValue(dato: ProyectoInfoDato): { label: string; value: string } | null {
  if (dato.clave === "num_viviendas" && dato.valorNumero != null) {
    return { label: "Viviendas", value: Math.round(dato.valorNumero).toLocaleString("es-ES") };
  }
  if (dato.clave === "sup_total_m2" && dato.valorNumero != null) {
    const n = dato.valorNumero;
    const value =
      n >= 1_000_000
        ? `${(n / 1_000_000).toLocaleString("es-ES", { maximumFractionDigits: 1 })} km²`
        : `${Math.round(n).toLocaleString("es-ES")} m²`;
    return { label: "Superficie", value };
  }
  if (dato.clave === "promotor") {
    const raw = dato.valor.split(/[,(—-]/)[0]?.trim() || dato.valor;
    return { label: "Impulsa", value: raw.length > 36 ? `${raw.slice(0, 34)}…` : raw };
  }
  return null;
}

function chips(info: ProyectoInfoExtra): { label: string; value: string; key: string }[] {
  const order = ["num_viviendas", "sup_total_m2", "promotor"];
  const out: { label: string; value: string; key: string }[] = [];
  for (const clave of order) {
    const dato = info.datos.find((row) => row.clave === clave && row.destacado) ?? info.datos.find((row) => row.clave === clave);
    if (!dato) continue;
    const chip = formatChipValue(dato);
    if (chip) out.push({ ...chip, key: clave });
  }
  return out;
}

function FuenteDisclosure({ dato }: { dato: ProyectoInfoDato }) {
  const parts = [
    FUENTE_LABEL[dato.fuenteTipo],
    dato.fuenteNombre,
    formatDay(dato.fuenteFecha),
    CONFIANZA_LABEL[dato.confianza],
  ].filter(Boolean);
  if (!parts.length && !dato.extracto && !dato.fuenteUrl) return null;
  const text = parts.join(" · ");
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">Fuente</summary>
      {dato.extracto ? <p className="mt-1 text-sm italic text-slate-600">“{dato.extracto}”</p> : null}
      <p className="mt-1 text-xs text-slate-500">
        {dato.fuenteUrl ? (
          <a
            href={dato.fuenteUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-slate-300 underline-offset-2 hover:text-slate-700"
          >
            {text || "Abrir fuente"}
          </a>
        ) : (
          text
        )}
      </p>
    </details>
  );
}

function DatoRow({ dato }: { dato: ProyectoInfoDato }) {
  return (
    <div className="border-b border-slate-100 py-3 last:border-0">
      <p className="text-xs font-medium text-slate-500">{dato.etiqueta}</p>
      <p className="mt-1 text-sm leading-relaxed text-slate-900">{dato.valor}</p>
      <FuenteDisclosure dato={dato} />
    </div>
  );
}

function BloqueList({ info, bloque }: { info: ProyectoInfoExtra; bloque: ProyectoInfoBloque }) {
  const rows = info.datos.filter((dato) => dato.bloque === bloque && dato.clave !== "nombre_publico");
  if (!rows.length) return null;
  return (
    <section>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {PROYECTO_INFO_BLOQUE_LABEL[bloque]}
      </h3>
      <div className="mt-1">
        {rows.map((dato) => (
          <DatoRow key={`${dato.orden}-${dato.etiqueta}`} dato={dato} />
        ))}
      </div>
    </section>
  );
}

function HallazgoItem({ hallazgo }: { hallazgo: ProyectoInfoHallazgo }) {
  return (
    <li>
      <p className="text-sm font-semibold text-slate-900">{hallazgo.titulo}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{hallazgo.cuerpo}</p>
      {hallazgo.fuenteNombre || hallazgo.fuenteUrl ? (
        <p className="mt-1 text-xs text-slate-500">
          {hallazgo.fuenteUrl ? (
            <a
              href={hallazgo.fuenteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-slate-300 underline-offset-2 hover:text-slate-700"
            >
              {hallazgo.fuenteNombre || "Fuente"}
              {formatDay(hallazgo.fuenteFecha) ? ` · ${formatDay(hallazgo.fuenteFecha)}` : ""}
            </a>
          ) : (
            <>
              {hallazgo.fuenteNombre}
              {formatDay(hallazgo.fuenteFecha) ? ` · ${formatDay(hallazgo.fuenteFecha)}` : ""}
            </>
          )}
        </p>
      ) : null}
    </li>
  );
}

export function ProyectoInfoLead({
  info,
  stacked = false,
}: {
  info: ProyectoInfoExtra;
  stacked?: boolean;
}) {
  const destacados = chips(info);
  if (!destacados.length) return null;
  return (
    <div className={stacked ? "grid h-full grid-rows-3 gap-2" : "mb-4 grid gap-2 sm:grid-cols-3"}>
      {destacados.map((dato) => (
        <div
          key={dato.key}
          className="flex flex-col justify-center rounded-xl bg-white px-3 py-2.5 ring-1 ring-slate-200"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{dato.label}</p>
          <p className="mt-0.5 text-base font-bold leading-snug text-slate-900">{dato.value}</p>
        </div>
      ))}
    </div>
  );
}

export function ProyectoInfoTabPanel({
  info,
  tab,
  tramitacion,
}: {
  info: ProyectoInfoExtra;
  tab: ProyectoInfoTabId;
  tramitacion?: SigmaVisorTramite[] | null;
}) {
  if (tab === "relato") {
    return (
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Qué está pasando</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{info.resumen}</p>
      </div>
    );
  }

  if (tab === "datos") {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-slate-900">Datos</h2>
        <div className="grid gap-8 lg:grid-cols-2">
          {DATOS_COLUMNAS.map((bloques) => (
            <div key={bloques.join("-")} className="space-y-6">
              {bloques.map((bloque) => (
                <BloqueList key={bloque} info={info} bloque={bloque} />
              ))}
            </div>
          ))}
        </div>
        {info.huecos ? (
          <p className="text-sm leading-relaxed text-slate-600">
            <span className="font-semibold text-slate-700">Aún no consta: </span>
            {info.huecos}
          </p>
        ) : null}
      </div>
    );
  }

  if (tab === "cronologia") {
    const rows = info.datos.filter((dato) => dato.bloque === "cronologia");
    return (
      <div className="space-y-8">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Cronología</h2>
          <div className="mt-3">
            {rows.map((dato) => (
              <DatoRow key={`${dato.orden}-${dato.etiqueta}`} dato={dato} />
            ))}
          </div>
        </div>
        {tramitacion && tramitacion.length > 0 ? (
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Tramitación del ayuntamiento</h3>
            <div className="mt-4">
              <TramitacionTimeline rows={tramitacion} />
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  const prensa = info.datos.filter((dato) => dato.bloque === "prensa");
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Prensa</h2>
        {prensa.length > 0 ? (
          <div className="mt-3">
            {prensa.map((dato) => (
              <DatoRow key={`${dato.orden}-${dato.etiqueta}`} dato={dato} />
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">Sin recortes de prensa en la ficha.</p>
        )}
      </div>
      {info.hallazgos.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Otras notas</h3>
          <ul className="mt-3 space-y-4">
            {info.hallazgos.map((hallazgo) => (
              <HallazgoItem key={`${hallazgo.orden}-${hallazgo.titulo}`} hallazgo={hallazgo} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
